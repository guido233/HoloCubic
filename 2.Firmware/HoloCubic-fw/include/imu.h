#ifndef IMU_H
#define IMU_H

#include <stdint.h>
#include <I2Cdev.h>
#include <MPU6050.h>
#include "lv_port_indev.h"

#define IMU_I2C_SDA 32 
#define IMU_I2C_SCL 33


extern int32_t encoder_diff;
extern lv_indev_state_t encoder_state;

class IMU
{
private:
	MPU6050 imu;
	bool ready = false;
	bool flag = true;
	int16_t ax = 0, ay = 0, az = 0;
	int16_t gx = 0, gy = 0, gz = 0;

	uint32_t last_update_time = 0;
	bool readMotion();
	void clearMotion();

public:
	// A zero timeout makes one connection attempt. Failure leaves input released.
	bool init(uint32_t timeout_ms = 1000);
	bool isReady() const;

	void update(uint32_t interval_ms);

	int16_t getAccelX() const;
	int16_t getAccelY() const;
	int16_t getAccelZ() const;

	int16_t getGyroX() const;
	int16_t getGyroY() const;
	int16_t getGyroZ() const;

};

#endif
