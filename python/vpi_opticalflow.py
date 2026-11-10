"""Display VPI optical flow for numbered JPG image sequences.

Run: python python/vpi_opticalflow.py [folder] [--no-display --max-frames 30]
CPU (default) and CUDA use VPI sparse Lucas-Kanade flow. OFA uses NVIDIA
Optical Flow SDK through a CUDA-enabled OpenCV build with cudaoptflow,
for discrete GPUs such as RTX 3090. Press Q or Esc to quit.
"""

import argparse
from pathlib import Path
import random

import cv2
import numpy as np
import vpi


def sequence_frames(directory: Path) -> list[Path]:
    return sorted(
        (p for p in directory.iterdir()
         if p.is_file() and p.suffix.lower() == ".jpg" and p.stem.isdecimal()),
        key=lambda p: (int(p.stem), p.name),
    )


def choose_sequence(directory: Path) -> Path:
    folders = sorted({
        p.parent for p in directory.rglob("*")
        if p.is_file() and p.suffix.lower() == ".jpg" and p.stem.isdecimal()
    })
    folders = [p for p in folders if len(sequence_frames(p)) >= 2]
    if not folders:
        raise FileNotFoundError(f"No numbered JPG sequences with at least two frames in {directory}")
    return random.choice(folders)


def create_nvidia_flow(size: tuple[int, int]):
    api = getattr(cv2, "cuda_NvidiaOpticalFlow_2_0", None)
    if api is None:
        api = getattr(cv2.cuda, "NvidiaOpticalFlow_2_0", None)
    if api is None:
        raise RuntimeError(
            "--backend ofa requires OpenCV built with CUDA, opencv_contrib "
            "cudaoptflow and NVIDIA Optical Flow SDK support. This cv2 build "
            "does not expose NvidiaOpticalFlow_2_0. Use --backend cpu or cuda "
            "for VPI sparse flow."
        )
    if cv2.cuda.getCudaEnabledDeviceCount() < 1:
        raise RuntimeError("No CUDA device is accessible to this OpenCV build")
    # Default SDK settings; keep one instance for the entire sequence.
    return api.create(size)


def flow_image(flow: np.ndarray) -> np.ndarray:
    magnitude, angle = cv2.cartToPolar(flow[..., 0], flow[..., 1], angleInDegrees=True)
    hsv = np.empty((*magnitude.shape, 3), dtype=np.float32)
    hsv[..., 0] = angle
    hsv[..., 1] = 1.0
    hsv[..., 2] = np.clip(magnitude / 5.0, 0.0, 1.0)
    return (cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR) * 255).astype(np.uint8)


def sparse_flow(previous, current, backend) -> np.ndarray:
    # Detect afresh for each pair so lost tracks do not accumulate.
    with vpi.Backend.CPU:
        points, scores = previous.harriscorners(strength=0.1, sensitivity=0.01)
    with points.lock_cpu() as data, scores.rlock_cpu() as strengths:
        order = np.argsort(strengths, kind="stable")[::-1]
        data[:] = data[order]
        points.size = min(points.size, 500)
    visualization = cv2.cvtColor(current.cpu(), cv2.COLOR_GRAY2BGR)
    if points.size == 0:
        return visualization
    with backend:
        tracker = vpi.OpticalFlowPyrLK(previous, points, 3)
        tracked, status = tracker(current)
    with points.rlock_cpu() as start, tracked.rlock_cpu() as end, status.rlock_cpu() as flags:
        for a, b, flag in zip(start, end, flags):
            if flag == 0:  # VPI marks successful tracks with zero.
                p = tuple(np.rint(a).astype(int))
                q = tuple(np.rint(b).astype(int))
                cv2.arrowedLine(visualization, p, q, (0, 255, 0), 1, tipLength=0.3)
    return visualization


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    default_data = root / "Data"
    if not default_data.is_dir():
        default_data = root / "data"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", nargs="?", type=Path, help="Folder containing numbered JPG frames")
    parser.add_argument("--data-dir", type=Path, default=default_data)
    parser.add_argument("--no-display", action="store_true", help="Process without GUI windows")
    parser.add_argument("--max-frames", type=int, help="Limit the number of input frames")
    parser.add_argument("--fps", type=float, default=30.0, help="Display frame rate (default: 30)")
    parser.add_argument("--backend", choices=("cpu", "cuda", "ofa"), default="cpu")
    args = parser.parse_args()
    if args.max_frames is not None and args.max_frames < 2:
        parser.error("--max-frames must be at least 2")
    if not np.isfinite(args.fps) or args.fps <= 0:
        parser.error("--fps must be finite and positive")

    folder = args.folder if args.folder is not None else choose_sequence(args.data_dir)
    frames = sequence_frames(folder)
    if len(frames) < 2:
        raise ValueError(f"At least two numbered JPG frames are required in {folder}")
    if args.max_frames is not None:
        frames = frames[:args.max_frames]
    print(f"Input: {folder} ({len(frames)} frames, numeric order)")
    previous = None
    frame_shape = None
    frame_count = 0
    backend = None if args.backend == "ofa" else getattr(vpi.Backend, args.backend.upper())
    nvidia_flow = None
    try:
        delay = max(1, round(1000 / args.fps))
        for frame_path in frames:
            frame = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
            if frame is None:
                raise RuntimeError(f"Cannot read image: {frame_path}")
            if frame_shape is not None and frame.shape != frame_shape:
                raise ValueError(f"Frame dimensions changed at {frame_path}")
            frame_shape = frame.shape
            if args.backend == "ofa":
                if nvidia_flow is None:
                    nvidia_flow = create_nvidia_flow((frame.shape[1], frame.shape[0]))
                current = cv2.cuda_GpuMat()
                current.upload(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
            else:
                current = vpi.asimage(frame, vpi.Format.BGR8).convert(
                    vpi.Format.U8, backend=vpi.Backend.CPU
                )
            if previous is not None:
                if args.backend == "ofa":
                    vectors, _ = nvidia_flow.calc(previous, current, None)
                    # SDK helper converts fixed-point vectors to pixel units.
                    float_vectors = cv2.cuda_GpuMat()
                    nvidia_flow.convertToFloat(vectors, float_vectors)
                    visualization = flow_image(float_vectors.download())
                else:
                    visualization = sparse_flow(previous, current, backend)
                if not args.no_display:
                    visualization = cv2.resize(visualization, (frame.shape[1], frame.shape[0]))
                    cv2.imshow("Frame | Optical flow", np.hstack((frame, visualization)))
                    if cv2.waitKey(delay) & 0xFF in (27, ord("q")):
                        break
            previous = current
            frame_count += 1
        print(f"Processed {frame_count} frames")
    finally:
        if nvidia_flow is not None:
            nvidia_flow.collectGarbage()
        if not args.no_display:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
