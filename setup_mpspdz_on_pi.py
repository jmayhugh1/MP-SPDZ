#!/usr/bin/env python3
import subprocess
import os
import sys

def run_command(command, shell=True, check=True):
    """Runs a shell command and prints it."""
    print(f"\n[SETUP] Running: {command}")
    try:
        subprocess.run(command, shell=shell, check=check)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Command failed with exit code {e.returncode}")
        print("[INFO] If this is a permission error, try running with 'sudo'.")
        # We don't exit immediately for some errors (like pip) but for make/apt we probably should.
        if "apt-get" in command or "make" in command:
            sys.exit(1)

def main():
    print("=========================================")
    print("   MP-SPDZ Setup Script for Raspberry Pi 5")
    print("=========================================")

    # 0. Check location
    if not os.path.exists("Makefile") or not os.path.exists("CONFIG"):
        print("[ERROR] Please run this script from the root of the MP-SPDZ directory.")
        sys.exit(1)

    # 1. Install System Dependencies (APT)
    # Based on Dockerfile but adapted for Pi (generic clang)
    packages = [
        "automake", "build-essential", "clang", "cmake", "git",
        "libboost-dev", "libboost-thread-dev", "libclang-dev",
        "libgmp-dev", "libntl-dev", "libsodium-dev", "libssl-dev",
        "libgmp-dev", "libntl-dev", "libsodium-dev", "libssl-dev",
        "libtool", "vim", "gdb", "valgrind", "wget"
    ]
    
    print(f"[INFO] Installing {len(packages)} packages...")
    # Using sudo explicitly for apt commands
    run_command("sudo apt-get update")
    run_command(f"sudo apt-get install -y --no-install-recommends {' '.join(packages)}")

    # 2. Python Dependencies
    print("[INFO] Installing Python dependencies...")
    # Using python3 -m pip to ensure we use the explicit python3 environment
    # Adding --break-system-packages for recent Pi OS (Bookworm) which manages python externally
    # We try standard first, then fallback or just assume user handles venv if they want.
    # But for a "make it work" script on Pi, --break-system-packages is often what users need if not in venv.
    try:
        run_command("python3 -m pip install --upgrade pip ipython")
    except:
        print("[WARN] Standard pip install failed, trying with --break-system-packages (common for Pi OS Bookworm)...")
        run_command("python3 -m pip install --upgrade pip ipython --break-system-packages", check=False)

    # 3. Configure CONFIG.mine
    print("[INFO] Configuring CONFIG.mine for Pi 5 (ARM64)...")
    
    # Configuration optimized for Pi 5 (Cortex-A76)
    config_lines = [
        "",
        "# Added by setup_pi.py for Raspberry Pi 5",
        "ARCH = -march=native",
        "CXX = clang++", 
        "USE_NTL = 0",
        "MY_CFLAGS += -I/usr/local/include",
        "MY_LDLIBS += -Wl,-rpath -Wl,/usr/local/lib -L/usr/local/lib"
    ]
    
    # Check if CONFIG.mine exists to decide how to write/append
    mode = "a" if os.path.exists("CONFIG.mine") else "w"
    
    # Read existing to avoid duplicate appends if run multiple times
    existing_content = ""
    if os.path.exists("CONFIG.mine"):
        with open("CONFIG.mine", "r") as f:
            existing_content = f.read()

    with open("CONFIG.mine", mode) as f:
        for line in config_lines:
            if line.strip() and line in existing_content:
                continue # Skip duplicates
            if line:
                f.write(line + "\n")

    print("[INFO] CONFIG.mine updated.")

    # 4. Compile Dependencies
    print("=========================================")
    print("   Compiling Dependencies (ARM=1)")
    print("   This will download sse2neon and compile boost/libOTe")
    print("=========================================")

    # 4a. Fix Boost Download (Common failure point on Pi)
    boost_url = "https://sourceforge.net/projects/boost/files/boost/1.83.0/boost_1_83_0.tar.bz2/download"
    boost_file = "boost_1_83_0.tar.bz2"
    # Ensure libOTe submodule is active so we can put the file in the right place
    print("[INFO] Initializing libOTe submodule...")
    run_command("git submodule update --init --recursive deps/libOTe")
    
    boost_dir = "deps/libOTe/cryptoTools/thirdparty"
    boost_path = os.path.join(boost_dir, boost_file)
    
    if not os.path.exists(boost_dir):
        os.makedirs(boost_dir, exist_ok=True)
        
    if not os.path.exists(boost_path):
        print(f"[INFO] Manually downloading Boost 1.83.0 to avoid build script failure...")
        # using wget -O to handle redirects and output file
        run_command(f"wget -O {boost_path} {boost_url}")
    else:
        print(f"[INFO] Boost archive found at {boost_path}, skipping download.")
    
    # Check if we should use sudo for make? Usually no, unless installing to /usr/local/lib
    # The makefile does install to local/lib inside the dir, but some boost stuff might want system?
    # No, MP-SPDZ usually builds locally.
    # However, 'make clean-deps boost libote' might fail if permissions are wrong.
    # We'll run as current user.
    
    run_command("make clean-deps boost libote ARM=1")

    # 5. Setup SSL
    print("[INFO] Generating SSL keys...")
    run_command("./Scripts/setup-ssl.sh")

    # 6. Test Compilation (Mascot & Shamir)
    print("=========================================")
    print("   Compiling Mascot & Shamir Protocols")
    print("=========================================")
    run_command("make mascot-party.x shamir-party.x ARM=1 -j$(nproc)")

    print("\n[SUCCESS] Setup and compilation complete!")
    print("To run a test:")
    print("  ./Scripts/mascot.sh tutorial")
    print("  ./Scripts/shamir.sh tutorial")

if __name__ == "__main__":
    main()
