# OpenCV 4.14 with CUDA, NVIDIA Optical Flow, and Video Codecs

## Target and observed environment

Build **OpenCV 4.14.0** and matching `opencv_contrib` for the RTX 3090, using
system Python **3.12**. Include Python bindings for CUDA, NVIDIA hardware optical
flow, and NVDEC/NVENC video decoding/encoding.

This document describes a manual installation. No dependencies have been installed,
no build has been executed, and no system configuration has been changed while
preparing it.

| Component | Observed configuration |
| --- | --- |
| OS | Ubuntu 24.04.5 LTS, x86_64 |
| GPU | RTX 3090, reported by the user; compute capability 8.6 |
| Python | `/usr/bin/python3`, version 3.12.3 |
| System NumPy | 1.26.4 |
| VPI | 4.1.4, in `/usr/lib/python3/dist-packages/` |
| APT OpenCV | 4.6.0, in `/usr/lib/python3/dist-packages/` |
| CUDA on PATH | `/usr/bin/nvcc`, version 12.0 |
| CUDA under `/usr/local/cuda` | Symlink to `/usr/local/cuda-13.2`, nvcc 13.2 |
| Compiler / CMake | GCC 13.3; GCC 12 also available; CMake 3.28.3 |

The commands explicitly select **CUDA 13.2, GCC 13, and GPU architecture 8.6**.
The exact OpenCV 4.14.0 / CUDA 13.2 combination has **not been build-tested here**.
See troubleshooting if compatibility issues occur.

Install Python bindings into `/usr/local/lib/python3.12/dist-packages` and C++
libraries into `/usr/local/lib`. System Python searches this local package
location before `/usr/lib/python3/dist-packages`, allowing the new OpenCV to take
precedence without overwriting APT-owned OpenCV or VPI files. The Conda `vista`
environment will not automatically use this installation.

## 1. Check the driver and leave Conda

Use a fresh Bash terminal. Run `conda deactivate` until no Conda environment is
active. Do not add Conda library directories to `LD_LIBRARY_PATH`.

```bash
nvidia-smi
/usr/bin/python3 --version
/usr/local/cuda-13.2/bin/nvcc --version
/usr/bin/gcc-13 --version
/usr/bin/python3 -c 'import numpy, vpi; print(numpy.__version__, vpi.__version__)'
ldconfig -p | grep -E 'libcuda.so|libnvidia-opticalflow.so.1|libnvcuvid.so.1|libnvidia-encode.so.1'
```

During inspection, `nvidia-smi` could not communicate with the driver. The cause
has not been established; check again from the host terminal. Compilation may
work without GPU access, but CUDA and codec runtime checks require a working
driver and access to the GPU.

The driver must provide `libnvidia-opticalflow.so.1` for optical flow,
`libnvcuvid.so.1` for decoding, and `libnvidia-encode.so.1` for encoding. CUDA
Toolkit alone is insufficient. Never add CUDA or SDK stub directories to the
runtime library search path.

## 2. Install build dependencies

These commands install system packages when you execute them manually. A full
system upgrade is unnecessary. Do not use `sudo pip` or `--break-system-packages`.

```bash
sudo apt update
sudo apt install --no-install-recommends \
  build-essential gcc-13 g++-13 cmake ninja-build pkg-config git ca-certificates \
  python3-dev python3-numpy \
  libjpeg-dev libpng-dev libtiff-dev \
  libavcodec-dev libavformat-dev libavutil-dev libswscale-dev \
  libgtk-3-dev libtbb-dev
```

GTK supports `cv2.imshow`. cuDNN is unnecessary for optical flow and video
codecs, so CUDA DNN is disabled. FFmpeg supports video demuxing and regular
video I/O.

## 3. Download matching sources

Keep the following variables in the same terminal throughout the guide. Use
new directories rather than cloning over an existing checkout.

```bash
export OPENCV_VERSION=4.14.0
export OPENCV_WORK="$HOME/Downloads/opencv-cuda-${OPENCV_VERSION}"
export OPENCV_CUDA_ROOT=/usr/local/cuda-13.2
mkdir -p "$OPENCV_WORK"
git clone --branch "$OPENCV_VERSION" --depth 1 \
  https://github.com/opencv/opencv.git "$OPENCV_WORK/opencv"
git clone --branch "$OPENCV_VERSION" --depth 1 \
  https://github.com/opencv/opencv_contrib.git "$OPENCV_WORK/opencv_contrib"
git -C "$OPENCV_WORK/opencv" rev-parse HEAD
git -C "$OPENCV_WORK/opencv_contrib" rev-parse HEAD
```

Record both commit IDs and retain the configure/build logs for reproducibility.
The `cudaoptflow` configuration downloads NVIDIA optical flow headers; configure
therefore needs Internet access. This is separate from the Video Codec SDK below.

## 4. Prepare NVIDIA Video Codec SDK headers

Download and extract the official [NVIDIA Video Codec SDK](https://developer.nvidia.com/video-codec-sdk).
Select a release whose minimum driver requirement is satisfied by the host.
CUDA Toolkit version alone does not establish SDK/driver compatibility.

There is no separate codec engine to compile: OpenCV builds `cudacodec` against
SDK headers and NVIDIA driver libraries. This module provides Python wrappers
for `cv2.cudacodec.createVideoReader()` and `createVideoWriter()`, with GPU frame
buffers. Ordinary `cv2.VideoCapture` and `cv2.VideoWriter` do not automatically
switch to these APIs. The JPG sequence script does not currently use them.

Set the SDK path to your actual extracted directory. The version below is an
example, not an SDK detected on this machine:

```bash
export OPENCV_VIDEO_SDK="$HOME/Downloads/Video_Codec_SDK_12.2.72"
ls "$OPENCV_VIDEO_SDK/Interface/"{nvcuvid.h,cuviddec.h,nvEncodeAPI.h}
ldconfig -p | grep -E 'libnvcuvid.so.1|libnvidia-encode.so.1'
ls -l "$OPENCV_CUDA_ROOT/include/"{nvcuvid.h,cuviddec.h,nvEncodeAPI.h}
```

Missing headers in the last command are expected if not previously installed.
If they already exist, check versions and save copies before replacing them.
Install the missing SDK headers into the selected toolkit's include directory:

```bash
sudo install -m 0644 \
  "$OPENCV_VIDEO_SDK/Interface/nvcuvid.h" \
  "$OPENCV_VIDEO_SDK/Interface/cuviddec.h" \
  "$OPENCV_VIDEO_SDK/Interface/nvEncodeAPI.h" \
  "$OPENCV_CUDA_ROOT/include/"
```

This step modifies the toolkit when executed. Do not copy SDK stub libraries
into runtime directories or add SDK `Lib/.../stubs` to `LD_LIBRARY_PATH`.

## 5. Configure

The module list includes image I/O, display, video I/O, optical flow, CUDA, video
codecs, and Python bindings. Fast math is disabled to avoid unnecessary numerical
changes.

```bash
export OPENCV_NUMPY_INCLUDE="$(/usr/bin/python3 -c 'import numpy; print(numpy.get_include())')"
set -o pipefail
/usr/bin/cmake -S "$OPENCV_WORK/opencv" -B "$OPENCV_WORK/build" -G Ninja \
  -D CMAKE_BUILD_TYPE=Release \
  -D CMAKE_INSTALL_PREFIX=/usr/local \
  -D CMAKE_C_COMPILER=/usr/bin/gcc-13 \
  -D CMAKE_CXX_COMPILER=/usr/bin/g++-13 \
  -D CUDA_HOST_COMPILER=/usr/bin/gcc-13 \
  -D CUDA_TOOLKIT_ROOT_DIR="$OPENCV_CUDA_ROOT" \
  -D CUDA_NVCC_EXECUTABLE="$OPENCV_CUDA_ROOT/bin/nvcc" \
  -D WITH_CUDA=ON \
  -D CUDA_ARCH_BIN=8.6 \
  -D CUDA_ARCH_PTX= \
  -D WITH_CUBLAS=ON \
  -D WITH_CUDNN=OFF \
  -D OPENCV_DNN_CUDA=OFF \
  -D ENABLE_FAST_MATH=OFF \
  -D CUDA_FAST_MATH=OFF \
  -D OPENCV_EXTRA_MODULES_PATH="$OPENCV_WORK/opencv_contrib/modules" \
  -D BUILD_LIST=core,imgproc,imgcodecs,highgui,video,videoio,features2d,calib3d,optflow,cudev,cudaarithm,cudaimgproc,cudawarping,cudaoptflow,cudacodec,python3 \
  -D BUILD_opencv_cudacodec=ON \
  -D WITH_NVCUVID=ON \
  -D WITH_NVCUVENC=ON \
  -D BUILD_opencv_python2=OFF \
  -D BUILD_opencv_python3=ON \
  -D PYTHON3_EXECUTABLE=/usr/bin/python3 \
  -D PYTHON3_INCLUDE_DIR=/usr/include/python3.12 \
  -D PYTHON3_NUMPY_INCLUDE_DIRS="$OPENCV_NUMPY_INCLUDE" \
  -D OPENCV_PYTHON3_INSTALL_PATH=/usr/local/lib/python3.12/dist-packages \
  -D WITH_GTK=ON \
  -D WITH_QT=OFF \
  -D WITH_FFMPEG=ON \
  -D WITH_GSTREAMER=OFF \
  -D WITH_TBB=ON \
  -D OPENCV_GENERATE_PKGCONFIG=ON \
  -D BUILD_TESTS=OFF \
  -D BUILD_PERF_TESTS=OFF \
  -D BUILD_EXAMPLES=OFF \
  -D BUILD_opencv_apps=OFF \
  2>&1 | tee "$OPENCV_WORK/configure.log"
```

Before building, check the summary and logs for:

- `NVIDIA CUDA: YES`, the selected toolkit version, and GPU architecture `86`.
- A message confirming NVIDIA Optical Flow API support.
- `Found NVCUVID` and `Found NVCUVENC`, without SDK dependency warnings.
- `cudaoptflow`, `cudacodec`, and `python3` in the modules being built.
- `/usr/bin/python3`, system NumPy, and the intended Python installation path.
- GTK and FFmpeg support.

A Python class being present does not prove the SDK is enabled: `create()` can
still fail if only the wrapper was compiled. Resolve header download or SDK
lookup failures before proceeding.

If CMake cannot find driver libraries automatically, add their actual paths from
`ldconfig -p` to the configure command using
`-D CUDA_nvcuvid_LIBRARY=/path/to/libnvcuvid.so.1` and
`-D CUDA_nvidia-encode_LIBRARY=/path/to/libnvidia-encode.so.1`.

## 6. Build and inspect before installation

```bash
/usr/bin/cmake --build "$OPENCV_WORK/build" --parallel 4 \
  2>&1 | tee "$OPENCV_WORK/build.log"
PYTHONPATH="$OPENCV_WORK/build/python_loader" /usr/bin/python3 - <<'PY'
import cv2
print(cv2.__version__, cv2.__file__)
assert cv2.__version__.startswith('4.14.')
print(cv2.getBuildInformation())
PY
```

Start with four parallel jobs; reduce to two if the compiler runs out of memory.
Check that the imported module comes from the build under test, rather than
APT. This guide does not run the full OpenCV test suite.

## 7. Install

Check for an existing manual installation in `/usr/local` first. If present,
save it and its installation manifest before replacing it. Keep the APT-owned
files in `/usr/lib/python3/dist-packages` and retain VPI.

```bash
ls -ld /usr/local/lib/python3.12/dist-packages/cv2*
sudo /usr/bin/cmake --install "$OPENCV_WORK/build"
sudo ldconfig
cp "$OPENCV_WORK/build/install_manifest.txt" "$OPENCV_WORK/install_manifest.saved.txt"
```

The first command may report no matching files on a clean local installation.
Keep the build directory and manifest: source installations are not managed by
APT and cannot be removed using `apt remove`.

## 8. Verify Python, CUDA, VPI, and NVIDIA optical flow

```bash
/usr/bin/python3 - <<'PY'
import cv2
import numpy as np
import vpi

print('OpenCV:', cv2.__version__, cv2.__file__)
print('VPI:', vpi.__version__, vpi.__file__)
assert cv2.__version__.startswith('4.14.')
assert cv2.__file__.startswith('/usr/local/')
assert cv2.cuda.getCudaEnabledDeviceCount() > 0

# Exercise GPU memory transfers.
a = np.arange(256 * 256, dtype=np.uint8).reshape(256, 256)
gpu = cv2.cuda_GpuMat()
gpu.upload(a)
assert np.array_equal(gpu.download(), a)

# Initialize and execute hardware optical flow.
nvof = cv2.cuda_NvidiaOpticalFlow_2_0.create((640, 480))
try:
    rng = np.random.default_rng(0)
    image = rng.integers(0, 256, (480, 640), dtype=np.uint8)
    previous = cv2.cuda_GpuMat()
    current = cv2.cuda_GpuMat()
    previous.upload(image)
    current.upload(np.roll(image, 2, axis=1))
    vectors, _ = nvof.calc(previous, current, None)
    pixels = cv2.cuda_GpuMat()
    nvof.convertToFloat(vectors, pixels)
    flow = pixels.download()
    assert flow.ndim == 3 and flow.shape[2] == 2
    assert np.isfinite(flow).all()
    print('NVIDIA flow:', flow.shape, flow.dtype)
finally:
    nvof.collectGarbage()
print('Smoke checks passed; algorithm accuracy has not been validated.')
PY
```

Run the project with the system interpreter:

```bash
cd /home/hoangqc/GitHub/vista
/usr/bin/python3 python/vpi_opticalflow.py --backend ofa --no-display --max-frames 3
/usr/bin/python3 python/vpi_opticalflow.py --backend ofa
```

In PyCharm, select `/usr/bin/python3` for this run configuration. Conda continues
to use its own OpenCV if installed. Do not inject all system `dist-packages`
into Conda through `PYTHONPATH`; that can mix incompatible NumPy and binary
library versions.

## 9. Verify video codec Python bindings

Replace the placeholder with a real H.264 video before running:

```bash
/usr/bin/python3 - <<'PY'
import cv2
assert hasattr(cv2, 'cudacodec')
assert hasattr(cv2.cudacodec, 'createVideoReader')
assert hasattr(cv2.cudacodec, 'createVideoWriter')
print('Python codec APIs available')
reader = cv2.cudacodec.createVideoReader('/absolute/path/to/input.mp4')
ok, frame = reader.nextFrame()
assert ok
print('Decoded GPU frame:', frame.size(), frame.type())
PY
```

This checks decoding one frame, not encoding. Validate NVENC separately with
your intended codec, frame format, output container, and a writable output path.
Neither codec execution nor this OpenCV build has been validated on this machine
while preparing the guide.

## 10. Troubleshooting

- **CUDA 12.0 selected instead of 13.2:** inspect the CMake cache and nvcc path.
  Use a new build directory when changing toolkit or compiler. There is no need
  to modify the global `/usr/local/cuda` symlink.
- **CUDA 13.2 compatibility errors:** this exact combination has not been tested.
  One fallback to evaluate is CUDA Toolkit 12.6 installed alongside the existing
  toolkit, with GCC/G++ 12. Follow NVIDIA's Ubuntu instructions and select
  `cuda-toolkit-12-6` rather than the `cuda` meta-package to avoid requesting a
  driver replacement. Installing another toolkit is a separate system change.
  Set `OPENCV_CUDA_ROOT=/usr/local/cuda-12.6`, select GCC/G++ 12 in all compiler
  options, and use a new build directory throughout the remaining commands.
- **Missing NVIDIA runtime libraries:** check the host driver and userspace
  packages. These libraries are not supplied by `pip install opencv-python`.
  Containers need NVIDIA runtime access and suitable `video,compute,utility`
  driver capabilities.
- **Missing codec headers:** check the selected toolkit's `include` directory
  and SDK version. Reconfigure in a fresh build directory after resolving them.
- **`No CUDA support`, or importing OpenCV 4.6/5.0:** inspect `sys.executable`,
  `cv2.__file__`, `PYTHONPATH`, `LD_LIBRARY_PATH`, and the IDE interpreter.
- **`No VIC hardware available`:** the RTX 3090 path uses OpenCV's NVIDIA
  Optical Flow SDK integration, not VPI's Jetson OFA/VIC backends.
- **Missing shared libraries after installation:** inspect `ldconfig -p` and
  run `ldd` on the installed cv2 extension. Ubuntu normally includes
  `/usr/local/lib` in its loader configuration; check before adding entries.
  Do not use Conda libraries or CUDA stubs to mask missing dependencies.

## References

- [Requested reference: OpenCV 4.10 / CUDA on Ubuntu 24.04](https://gist.github.com/raulqf/f42c718a658cddc16f9df07ecc627be7).
  Adapted for this machine rather than copying the author's GPU architecture,
  virtual environment, cuDNN, fast-math settings, or binding-copy procedure.
- [OpenCV 4.14.0 release](https://github.com/opencv/opencv/releases/tag/4.14.0).
- [Matching opencv_contrib release](https://github.com/opencv/opencv_contrib/releases/tag/4.14.0).
- [OpenCV Linux installation](https://docs.opencv.org/4.x/d7/d9f/tutorial_linux_install.html).
- [OpenCV 4.14.0 cudaoptflow configuration](https://github.com/opencv/opencv_contrib/blob/4.14.0/modules/cudaoptflow/CMakeLists.txt).
- [OpenCV 4.14.0 cudacodec and Python wrappers](https://github.com/opencv/opencv_contrib/blob/4.14.0/modules/cudacodec/CMakeLists.txt).
- [OpenCV 4.14.0 Video Codec SDK detection](https://github.com/opencv/opencv/blob/4.14.0/cmake/OpenCVDetectCUDAUtils.cmake).
- [NVIDIA Video Codec SDK](https://developer.nvidia.com/video-codec-sdk).
- [CUDA 12.6 Linux installation, for the fallback option](https://docs.nvidia.com/cuda/archive/12.6.3/cuda-installation-guide-linux/index.html).
