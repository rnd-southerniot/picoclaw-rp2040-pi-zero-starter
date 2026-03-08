"""
Gate 0 — Environment Setup Verification
Checks: MicroPython firmware, platform, memory

Pass criteria:
  - REPL responds
  - Platform = rp2
  - Implementation = micropython
"""

import sys
import gc


def run():
    print("=" * 40)
    print("GATE 0: Environment Check")
    print("=" * 40)

    passed = True

    # Check implementation
    impl = sys.implementation.name
    print(f"  Implementation: {impl}", end=" ")
    if impl == "micropython":
        print("✓")
    else:
        print("✗ (expected: micropython)")
        passed = False

    # Check platform
    platform = sys.platform
    print(f"  Platform:       {platform}", end=" ")
    if platform == "rp2":
        print("✓")
    else:
        print("✗ (expected: rp2)")
        passed = False

    # Check version
    ver = ".".join(str(v) for v in sys.implementation.version[:3])
    print(f"  Version:        {ver}")

    # Memory check
    gc.collect()
    free = gc.mem_free()
    print(f"  Free memory:    {free // 1024} KB")

    print("-" * 40)
    if passed:
        print("GATE 0: PASSED ✓")
    else:
        print("GATE 0: FAILED ✗")
    print()
    return passed


if __name__ == "__main__":
    run()
