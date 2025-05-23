from controller import Supervisor
import csv, math

# ───────────────────────────── user params ────────────────────────────────
FREQ_HZ  = 0.5                    # tripod-gait frequency
CSV_FILE = "expert_data.csv"      # where to store the log
# ──────────────────────────────────────────────────────────────────────────

print("Mantis expert logger started.")

robot      = Supervisor()
TIMESTEP   = int(robot.getBasicTimeStep())
is_super   = hasattr(robot, "getSelf")
robot_node = robot.getSelf() if is_super else None

# ─────────────── motors and their encoders ────────────────
MOTOR_NAMES = [
    "RPC","RPF","RPT",  "RMC","RMF","RMT",  "RAC","RAF","RAT",
    "LPC","LPF","LPT",  "LMC","LMF","LMT",  "LAC","LAF","LAT"
]
motors, encoders = [], []
for name in MOTOR_NAMES:
    m  = robot.getDevice(name)
    ps = m.getPositionSensor() if m else None
    if ps:  ps.enable(TIMESTEP)
    motors.append(m)
    encoders.append(ps)

# ─────────────── IMU (+ optional gyro / accelerometer) ───
imu  = robot.getDevice("inertial unit")
gyro = robot.getDevice("gyro")
acc  = robot.getDevice("accelerometer")
for s in (imu, gyro, acc):
    if s:
        s.enable(TIMESTEP)

# ─────────────── foot contact sensors ──────────────────────
FOOT_NAMES = ["LAS","LMS","LPS","RAS","RMS","RPS"]
feet = []
for name in FOOT_NAMES:
    ts = robot.getDevice(name)
    if ts: ts.enable(TIMESTEP)
    else:  print(f"[warn] foot sensor {name} not found")
    feet.append(ts)

# ─────────────── centre of mass (Supervisor only) ─────────
if is_super:
    robot_node = robot.getSelf()
else:
    robot_node = None

# ─────────────── hard‑coded tripod gait parameters ────────
aC,aF,aT = 0.25, 0.20,  0.05           # amplitudes
dC,dF,dT = 0.60, 0.80, -2.40           # offsets
pC,pF,pT = 0.00, 2.00,  2.50           # phases
A = [ aC, aF,-aT,-aC,-aF, aT,  aC, aF,-aT,  aC,-aF, aT, -aC, aF,-aT,  aC,-aF, aT]
D = [-dC, dF, dT, 0.0, dF, dT,  dC, dF, dT,  dC, dF, dT, 0.0, dF, dT, -dC, dF, dT]
P = [ pC, pF, pT, pC, pF, pT,  pC, pF, pT,  pC, pF, pT, pC, pF, pT,  pC, pF, pT]

# ─────────────── CSV header ───────────────────────────────
# time | 18 commands | imu_roll, imu_acc_norm | 18 encoders | 6 feet | com_x,y,z
header = (
    ["time"] +
    MOTOR_NAMES +
    ["imu_roll", "imu_acc_norm"] +
    [f"enc_{n}" for n in MOTOR_NAMES] +
    FOOT_NAMES +
    ["com_x", "com_y", "com_z"]
)

with open(CSV_FILE, "w", newline="") as fp:
    writer = csv.writer(fp)
    writer.writerow(header)

    # ───────────────────── main loop ──────────────────────
    while robot.step(TIMESTEP) != -1:
        t = robot.getTime()

        # ----- compute & send tripod gait set-points -----
        cmd = [
            A[i] * math.sin(2 * math.pi * FREQ_HZ * t + P[i]) + D[i]
            for i in range(18)
        ]
        for m, pos in zip(motors, cmd):
            m.setPosition(pos)

        # ----- sensors -----
        # IMU: roll + accel norm
        r, p, y = imu.getRollPitchYaw() if imu else (0.0, 0.0, 0.0)
        ax, ay, az = acc.getValues() if acc else (0.0, 0.0, 0.0)
        acc_norm = math.sqrt(ax*ax + ay*ay + az*az)
        imu_feats = [r, acc_norm]

        # encoders + feet
        enc_vals  = [ps.getValue() if ps else None for ps in encoders]
        foot_vals = [ts.getValue() if ts else None for ts in feet]

        # center of mass
        com_vals = robot_node.getCenterOfMass() if robot_node else (None, None, None)

        # ----- write one CSV row -----
        writer.writerow(
            [t]
            + cmd
            + imu_feats
            + enc_vals
            + foot_vals
            + list(com_vals)
        )

print("Finished; data saved to", CSV_FILE)
