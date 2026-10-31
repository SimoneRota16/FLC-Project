/*
 * pid_control.c -- closed-loop speed control of a DC motor with a PID.
 *
 * Part of the FLC 2026/27 project "Harden a C application with ASPIS"
 * (Politecnico di Milano). Written from scratch for ASPIS regression
 * testing and fault-injection campaigns.
 *
 * A first-order motor model is simulated for 2000 steps of 10 ms. A PID
 * controller (derivative on measurement with a low-pass filter, output
 * saturation and conditional-integration anti-windup) tracks a staircase
 * set-point while a load torque disturbance is applied. The speed sensor is
 * quantised like an incremental encoder. The program reports the integral
 * of the absolute error, the overshoot and the time spent in saturation.
 *
 * ASPIS features stressed:
 *   - single-precision floating point (typical of embedded controllers)
 *   - controller state kept in a global struct updated through a pointer
 *   - float-to-int conversions (sensor quantisation)
 *   - data-dependent branches (saturation, anti-windup)
 *
 * The results are printed with literal strings only, never with "%s" and a
 * string chosen at run time: on ASPIS b66a090 that makes the programs
 * hardened with EDDI crash (aspis-integration/reproducers/string_literal.c).
 *
 * Copyright (c) 2026 Alberto Rotolo, Simone Rota
 * SPDX-License-Identifier: MIT
 */
#include <stdio.h>
#include <stdlib.h>

/* ASPIS fault handlers: invoked when a data mismatch (EDDI family) or a
 * control-flow signature mismatch (CFCSS/RASM/RACFED) is detected. */
void DataCorruption_Handler(void) {
    fprintf(stderr, "FAULT_DETECTED: DataCorruption\n");
    exit(2);
}

void SigMismatch_Handler(void) {
    fprintf(stderr, "FAULT_DETECTED: SigMismatch\n");
    exit(3);
}

#define STEPS 2000
#define DT 0.01f

typedef struct {
    float kp, ki, kd;
    float integral;
    float prev_meas;
    float d_filtered;
    float out_min, out_max;
    float alpha; /* derivative low-pass coefficient */
} Pid;

typedef struct {
    float speed;  /* rad/s */
    float gain;   /* rad/s per volt */
    float tau;    /* time constant, s */
} Motor;

static Pid pid = {2.0f, 3.0f, 0.02f, 0.0f, 0.0f, 0.0f, -24.0f, 24.0f, 0.2f};
static Motor motor = {0.0f, 2.0f, 0.5f};
static int saturated_steps;

static float abs_f(float x) {
    return x < 0.0f ? -x : x;
}

static float setpoint_at(int k) {
    if (k < 500)
        return 10.0f;
    if (k < 1000)
        return 25.0f;
    if (k < 1500)
        return 5.0f;
    return 15.0f;
}

static float load_at(int k) {
    return (k >= 1200 && k < 1300) ? 1.5f : 0.0f;
}

/* encoder with 0.05 rad/s resolution */
static float quantise(float speed) {
    int ticks;
    if (speed >= 0.0f)
        ticks = (int)(speed * 20.0f + 0.5f);
    else
        ticks = -(int)(-speed * 20.0f + 0.5f);
    return (float)ticks / 20.0f;
}

static float pid_step(Pid *c, float setpoint, float meas) {
    float err = setpoint - meas;
    float deriv = -(meas - c->prev_meas) / DT;
    float u, candidate;
    c->d_filtered += c->alpha * (deriv - c->d_filtered);
    c->prev_meas = meas;
    candidate = c->integral + c->ki * err * DT;
    u = c->kp * err + candidate + c->kd * c->d_filtered;
    if (u > c->out_max) {
        u = c->out_max;
        saturated_steps++;
        if (err < 0.0f) /* integrate only if it helps leaving saturation */
            c->integral = candidate;
    } else if (u < c->out_min) {
        u = c->out_min;
        saturated_steps++;
        if (err > 0.0f)
            c->integral = candidate;
    } else {
        c->integral = candidate;
    }
    return u;
}

static void motor_step(Motor *m, float volts, float load) {
    m->speed += DT / m->tau * (m->gain * volts - m->speed) - DT * load * 4.0f;
}

int main(void) {
    float iae = 0.0f, max_overshoot = 0.0f, u = 0.0f, sp = 0.0f;
    float energy = 0.0f, step_dir = 0.0f;
    int k, last_change = 0, settled_at = -1, ok = 1;

    for (k = 0; k < STEPS; k++) {
        float meas, err;
        float new_sp = setpoint_at(k);
        if (new_sp != sp) {
            step_dir = (new_sp > sp) ? 1.0f : -1.0f;
            sp = new_sp;
            last_change = k;
            settled_at = -1;
        }
        meas = quantise(motor.speed);
        u = pid_step(&pid, sp, meas);
        motor_step(&motor, u, load_at(k));
        err = sp - motor.speed;
        iae += abs_f(err) * DT;
        energy += u * u * DT;
        /* overshoot measured in the direction of the last set-point step */
        if (k - last_change < 300 && step_dir * (motor.speed - sp) > max_overshoot)
            max_overshoot = step_dir * (motor.speed - sp);
        if (settled_at < 0 && abs_f(err) < 0.02f * sp)
            settled_at = k - last_change;
        if (k % 250 == 249)
            printf("t=%5.2fs sp=%5.1f speed=%8.4f u=%8.4f\n", (k + 1) * DT, sp,
                   motor.speed, u);
    }
    printf("IAE %.4f, max overshoot %.4f, energy %.3f\n", iae, max_overshoot, energy);
    printf("saturated steps %d, last settling %d steps\n", saturated_steps, settled_at);
    if (abs_f(motor.speed - sp) > 0.1f || settled_at < 0)
        ok = 0;
    if (ok)
        printf("SUCCESS\n");
    else
        printf("FAIL\n");
    return ok ? 0 : 1;
}
