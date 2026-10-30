#!/usr/bin/env python3
"""BOM/replacement regressions using the actual controlled KiCad instances.

No KiCad export, DRC, design mutation, or permanent BOM output is performed.
The grouping tests exercise the production CSV rows with all real instances;
negative tests inject procurement mistakes into copies of those instances.
"""
import copy
import csv
import io
import unittest
from collections import Counter
from contextlib import redirect_stderr
from datetime import date

from export_bom import (BASE, acceptance_note, argument_parser, document_date,
                        grouped_rows, procurement)
from revise_schematic import alln, parse, prop
from verify_hardware import Checks, extend_electrical, main_electrical, pcb_circuit


class ProcurementMetadataTests(unittest.TestCase):
    def test_selected_manufacturers_and_official_sources(self):
        for mpn, maker, host in [
            ('TPS22918DBVT', 'Texas Instruments', 'www.ti.com'),
            ('RTT022000FTH', 'RALEC', 'www.ralec.com'),
            ('GRM188R71E105KA12D', 'Murata', 'ds.murata.com'),
        ]:
            with self.subTest(mpn=mpn):
                manufacturer, _, _, source = procurement(mpn)
                self.assertEqual(maker, manufacturer)
                self.assertTrue(source.startswith('https://' + host + '/'))

    def test_legacy_switch_identity_remains_supported(self):
        self.assertEqual('Texas Instruments', procurement('TPS22918DBVR')[0])

    def test_switch_channel_snapshot_is_dated_without_dynamic_price(self):
        note = acceptance_note('MainBoard', 'U6', 'TPS22918DBVT', '')
        self.assertIn('2026-10-30', note)
        self.assertIn('需订货', note)
        self.assertIn('250pcs', note)
        for price_marker in ('¥', '￥', 'RMB'):
            self.assertNotIn(price_marker, note)

    def test_resistor_note_preserves_uart_and_assembly_conditions(self):
        note = acceptance_note('MainBoard', 'R3', 'RTT022000FTH', '')
        self.assertIn('UART', note)
        self.assertIn('200ohm', note)
        self.assertIn('原厂推荐图有差异', note)
        self.assertIn('工艺须验收', note)

    def test_client_date_can_be_selected_without_host_midnight_drift(self):
        args = argument_parser().parse_args(['--date', '2026-10-30'])
        self.assertEqual('2026-10-30', document_date(args.export_date))
        self.assertEqual('2026-10-30', document_date('2026-10-30'))

    def test_default_date_keeps_existing_behavior(self):
        self.assertIsNone(argument_parser().parse_args([]).export_date)
        self.assertEqual(date.today().isoformat(), document_date())

    def test_invalid_client_date_is_rejected_before_export(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            argument_parser().parse_args(['--date', '2026-02-30'])
        self.assertEqual(2, error.exception.code)


class ActualInstanceGroupingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parts = []
        for board in ('MainBoard', 'ExtendBoard'):
            schematic = parse((BASE / board / (board + '.kicad_sch')).read_text())
            for symbol in alln(schematic, 'symbol'):
                ref = str(prop(symbol, 'Reference')[2])
                if ref.startswith('#'):
                    continue
                mpn = str(prop(symbol, 'MPN')[2])
                manufacturer, status, note, source = procurement(mpn)
                cls.parts.append({
                    'board': board, 'reference': ref, 'quantity': 1,
                    'value': str(prop(symbol, 'Value')[2]), 'mpn': mpn,
                    'manufacturer': manufacturer, 'supply_status': status,
                    'acceptance_note': acceptance_note(board, ref, mpn, note),
                    'source_url': source,
                })

    def test_all_69_sites_survive_serialization_into_38_mpn_groups(self):
        self.assertEqual({'MainBoard': 58, 'ExtendBoard': 11},
                         dict(Counter(p['board'] for p in self.parts)))
        grouped = grouped_rows(self.parts)
        self.assertEqual(38, len(grouped))
        output = io.StringIO()
        csv.writer(output).writerows(grouped)
        output.seek(0)
        readback = list(csv.reader(output))
        self.assertEqual(69, sum(int(row[2]) for row in readback))
        expected = Counter(p['board'] + ':' + p['reference'] for p in self.parts)
        actual = Counter(site for row in readback for site in row[4].split(', '))
        self.assertEqual(69, len(expected))
        self.assertEqual(expected, actual)

    def test_shared_25v_group_contains_both_and_only_the_two_selected_sites(self):
        grouped = {row[0]: row for row in grouped_rows(self.parts)}
        row = grouped['GRM188R71E105KA12D']
        self.assertEqual(2, row[2])
        self.assertEqual({'MainBoard:C24', 'ExtendBoard:C4'}, set(row[4].split(', ')))
        self.assertIn('BH1750 DVI', row[6])
        self.assertIn('5V本地旁路', row[6])

    def test_main_c4_keeps_22uf_bulk_group_and_its_own_acceptance_note(self):
        grouped = {row[0]: row for row in grouped_rows(self.parts)}
        bulk = grouped['GRM21BR61E226ME44L']
        self.assertEqual(4, bulk[2])
        self.assertEqual({'MainBoard:C2', 'MainBoard:C3', 'MainBoard:C4', 'MainBoard:C13'},
                         set(bulk[4].split(', ')))
        part = next(p for p in self.parts if (p['board'], p['reference']) == ('MainBoard', 'C4'))
        self.assertIn('22uF', part['acceptance_note'])
        self.assertNotIn('C86020', part['acceptance_note'])

    def test_equivalent_100nf_and_point1uf_spellings_still_group_together(self):
        row = next(r for r in grouped_rows(self.parts) if r[0] == 'GRM155R71C104KA88D')
        self.assertIn('100nF', row[1])
        self.assertIn('0.1uF', row[1])
        self.assertIn('MainBoard:C5', row[4])
        self.assertIn('ExtendBoard:C1', row[4])

    def test_bulk_c4_mislabelled_with_1uf_mpn_is_rejected(self):
        parts = copy.deepcopy(self.parts)
        next(p for p in parts if (p['board'], p['reference']) == ('MainBoard', 'C4'))['mpn'] = 'GRM188R71E105KA12D'
        with self.assertRaisesRegex(ValueError, 'Conflicting electrical values'):
            grouped_rows(parts)

    def test_duplicate_instance_cannot_silently_inflate_a_purchasing_group(self):
        parts = copy.deepcopy(self.parts)
        parts.append(copy.deepcopy(next(p for p in parts if p['reference'] == 'C24')))
        with self.assertRaisesRegex(ValueError, 'Duplicate BOM instance: MainBoard:C24'):
            grouped_rows(parts)


class SelectedMpnMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main, _, _ = pcb_circuit(BASE / 'MainBoard/MainBoard.kicad_pcb')
        cls.extend, _, _ = pcb_circuit(BASE / 'ExtendBoard/ExtendBoard.kicad_pcb')

    def test_selected_native_parts_keep_existing_electrical_invariants(self):
        checks = Checks()
        main_electrical(checks, self.main)
        extend_electrical(checks, self.extend, self.main)
        self.assertEqual([], [r for r in checks.rows if not r['passed']])

    def test_main_mpn_rollbacks_are_rejected_even_when_values_do_not_change(self):
        for ref, old_mpn, assertion in [
            ('C24', 'GRM188R71C105KA12D', 'BH1750 DVI selected 25V MPN'),
            ('U6', 'TPS22918DBVR', 'Load switch selected DBVT MPN'),
            ('R3', 'RC0402FR-07200RL', 'UART series resistor selected RALEC MPN'),
        ]:
            with self.subTest(reference=ref):
                mutated = copy.deepcopy(self.main)
                mutated.mpns[ref] = old_mpn
                self.assertEqual(self.main.values, mutated.values)
                checks = Checks()
                main_electrical(checks, mutated)
                self.assertFalse(next(r for r in checks.rows if r['check'] == assertion)['passed'])

    def test_extend_c4_mpn_rollback_is_rejected_without_changing_1uf(self):
        mutated = copy.deepcopy(self.extend)
        mutated.mpns['C4'] = 'GRM188R71A105KA61D'
        self.assertEqual(self.extend.values, mutated.values)
        checks = Checks()
        extend_electrical(checks, mutated)
        self.assertFalse(next(r for r in checks.rows if r['check'] == 'Display 5V bypass selected 25V MPN')['passed'])


if __name__ == '__main__':
    unittest.main()
