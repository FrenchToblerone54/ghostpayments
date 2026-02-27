import os

def write_env(updates):
    env_path = os.getenv("ENV_PATH", "/etc/ghostpayments/.env")
    lines = open(env_path).readlines() if os.path.exists(env_path) else []
    result = []
    written = set()
    for line in lines:
        key = line.split("=")[0].strip()
        if key in updates:
            result.append(f"{key}={updates[key]}\n")
            written.add(key)
        else:
            result.append(line)
    for key, val in updates.items():
        if key not in written:
            result.append(f"{key}={val}\n")
    open(env_path, "w").writelines(result)
