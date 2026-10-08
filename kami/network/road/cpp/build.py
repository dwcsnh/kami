"""Build the C++ road router in place: ``python -m kami.network.road.cpp.build``.

Needs Cython (``pip install cython``) and a C++17 compiler. Re-run after changing the ``.cpp``/``.h``/``.pyx`` files.
"""
from __future__ import annotations

import os
import platform
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]          # folder that contains the ``kami`` package


def main() -> int:
    try:
        from Cython.Build import cythonize
        from setuptools import Extension, setup
    except ImportError as exc:
        print(f"cannot build the C++ router: {exc}. Install Cython: pip install cython", file=sys.stderr)
        return 1
    flags = ["/std:c++17"] if platform.system() == "Windows" else ["-std=c++17", "-O3"]
    ext = Extension("kami.network.road.cpp._router", sources=[str((HERE / "_router.pyx").relative_to(ROOT))],
                    include_dirs=[str(HERE)], language="c++", extra_compile_args=flags)
    cwd = os.getcwd()
    os.chdir(ROOT)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            setup(name="kami-road-router", ext_modules=cythonize([ext], language_level=3, quiet=True,
                                                                 build_dir=tmp),
                  script_args=["build_ext", "--inplace", "--build-temp", tmp, "--build-lib", tmp], zip_safe=False)
    finally:
        os.chdir(cwd)
    from importlib import invalidate_caches

    invalidate_caches()
    print("built", next(HERE.glob("_router*.so"), None) or next(HERE.glob("_router*.pyd"), None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
