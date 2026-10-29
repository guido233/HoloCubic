#include "imu.h"

namespace
{
constexpr uint16_t i2c_timeout_ms = 50;

bool isConnected()
{
	uint8_t identity = 0;
	return I2Cdev::readByte(MPU6050_DEFAULT_ADDRESS, MPU6050_RA_WHO_AM_I,
		&identity, i2c_timeout_ms) == 1 && (identity & 0x7e) == 0x68;
}

int16_t readAxis(const uint8_t* bytes)
{
	return static_cast<int16_t>((static_cast<uint16_t>(bytes[0]) << 8) | bytes[1]);
}
}

bool IMU::init(uint32_t timeout_ms)
{
	ready = false;
	clearMotion();
	if (!Wire.begin(IMU_I2C_SDA, IMU_I2C_SCL)) return false;
	Wire.setTimeOut(i2c_timeout_ms);
	Wire.setClock(400000);

	const uint32_t started = static_cast<uint32_t>(millis());
	while (true)
	{
		if (isConnected())
		{
			imu.initialize();
			if (readMotion())
			{
				ready = true;
				last_update_time = static_cast<uint32_t>(millis());
				return true;
			}
		}

		const uint32_t elapsed = static_cast<uint32_t>(millis()) - started;
		if (elapsed >= timeout_ms) return false;
		delay((timeout_ms - elapsed < 10) ? timeout_ms - elapsed : 10);
	}
}

bool IMU::isReady() const
{
	return ready;
}

void IMU::clearMotion()
{
	ax = ay = az = gx = gy = gz = 0;
	flag = true;
	encoder_diff = 0;
	encoder_state = LV_INDEV_STATE_RELEASED;
}

bool IMU::readMotion()
{
	uint8_t bytes[14] = {};
	// getMotion6() in the bundled driver ignores short reads; check the count here.
	if (I2Cdev::readBytes(MPU6050_DEFAULT_ADDRESS, MPU6050_RA_ACCEL_XOUT_H,
		sizeof(bytes), bytes, i2c_timeout_ms) != sizeof(bytes))
	{
		clearMotion();
		return false;
	}
	ax = readAxis(bytes);
	ay = readAxis(bytes + 2);
	az = readAxis(bytes + 4);
	gx = readAxis(bytes + 8);
	gy = readAxis(bytes + 10);
	gz = readAxis(bytes + 12);
	return true;
}

void IMU::update(uint32_t interval_ms)
{
	if (!ready) return;
	const uint32_t now = static_cast<uint32_t>(millis());
	if (static_cast<uint32_t>(now - last_update_time) < interval_ms) return;
	last_update_time = now;
	if (!readMotion())
	{
		ready = false;
		return;
	}

	if (ay > 3000 && flag)
	{
		encoder_diff--;
		flag = false;
	}
	else if (ay < -3000 && flag)
	{
		encoder_diff++;
		flag = false;
	}
	else
	{
		flag = true;
	}
	encoder_state = (ax > 10000) ? LV_INDEV_STATE_PRESSED : LV_INDEV_STATE_RELEASED;
}

int16_t IMU::getAccelX() const
{
	return ax;
}

int16_t IMU::getAccelY() const
{
	return ay;
}

int16_t IMU::getAccelZ() const
{
	return az;
}

int16_t IMU::getGyroX() const
{
	return gx;
}

int16_t IMU::getGyroY() const
{
	return gy;
}

int16_t IMU::getGyroZ() const
{
	return gz;
}
