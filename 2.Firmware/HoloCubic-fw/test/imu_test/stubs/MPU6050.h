#pragma once

#define MPU6050_DEFAULT_ADDRESS 0x68
#define MPU6050_RA_WHO_AM_I 0x75
#define MPU6050_RA_ACCEL_XOUT_H 0x3b

extern int test_initializations;

struct MPU6050
{
    void initialize() { ++test_initializations; }
};
