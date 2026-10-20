import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description='Training YOLOv8 untuk dua gestur tangan.')
    parser.add_argument('--epochs', type=int, default=80)
    parser.add_argument('--batch', type=int, default=8)
    parser.add_argument('--imgsz', type=int, default=640)
    parser.add_argument('--device', default='cpu', help='cpu atau 0 untuk CUDA GPU')
    parser.add_argument('--data', type=Path, default=ROOT / 'datasets/feeding/data.yaml')
    parser.add_argument('--resume', type=Path)
    args = parser.parse_args()
    from ultralytics import YOLO

    if not args.data.exists():
        raise SystemExit('Jalankan python prepare_dataset.py terlebih dahulu.')
    if args.resume:
        model = YOLO(str(args.resume))
        model.train(resume=True)
    else:
        model = YOLO('yolov8n.pt')
        model.train(data=str(args.data.resolve()), epochs=args.epochs, batch=args.batch,
                    imgsz=args.imgsz, device=args.device, workers=0, seed=42,
                    project=str(ROOT / 'runs/detect'), name='gesture-model', exist_ok=False)
    best = Path(model.trainer.best)
    if best.is_file():
        print('Model terbaik:', best)
        metrics = YOLO(str(best)).val(data=str(args.data.resolve()), split='test', device=args.device)
        report = ROOT / 'verification' / 'test-metrics.json'
        report.parent.mkdir(exist_ok=True)
        report.write_text(json.dumps(metrics.results_dict, indent=2), encoding='utf-8')
        print('Metrik test:', report)


if __name__ == '__main__':
    main()
