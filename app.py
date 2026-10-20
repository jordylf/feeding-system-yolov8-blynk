"""Laptop webcam -> custom YOLOv8 -> Blynk HTTPS -> ESP32 servo."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import time

from blynk_client import BlynkClient, BlynkError
from gesture_control import GestureGate, normalize_label

ROOT = Path(__file__).resolve().parent


def main():
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env', encoding='utf-8-sig')
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default=os.getenv('MODEL_PATH', 'runs/detect/gesture-model/weights/best.pt'))
    parser.add_argument('--camera', type=int, default=int(os.getenv('CAMERA_INDEX', '0')))
    parser.add_argument('--confidence', type=float, default=0.70)
    parser.add_argument('--hold', type=float, default=1.0)
    parser.add_argument('--dry-run', action='store_true', help='Deteksi tanpa koneksi/perintah Blynk')
    args = parser.parse_args()
    if not 0 < args.confidence <= 1 or args.hold <= 0:
        parser.error('confidence harus >0 sampai 1; hold harus >0.')
    model_path = Path(args.model)
    if not model_path.is_absolute():
        model_path = ROOT / model_path
    if not model_path.is_file():
        raise SystemExit('Model belum ada. Jalankan prepare_dataset.py dan train.py terlebih dahulu.')
    token = os.getenv('BLYNK_AUTH_TOKEN', '')
    if not args.dry_run and (not token or token.startswith('ISI_')):
        raise SystemExit('Isi BLYNK_AUTH_TOKEN pada .env, atau gunakan --dry-run.')
    import cv2
    from ultralytics import YOLO

    model = YOLO(str(model_path))
    names = model.names.values() if isinstance(model.names, dict) else model.names
    if {normalize_label(name) for name in names} != {'finger up', 'palm open'}:
        raise SystemExit('Gunakan model hasil training dataset gestur, bukan model COCO bawaan.')
    client = None if args.dry_run else BlynkClient(token, os.getenv('BLYNK_SERVER', 'https://blynk.cloud'))
    cap = cv2.VideoCapture(args.camera)
    gate = GestureGate(hold_seconds=args.hold)
    status, snapshot, pending, kind = 'DRY RUN' if args.dry_run else 'Menghubungkan Blynk...', {}, None, None
    last_poll = float('-inf')
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        if not cap.isOpened():
            raise SystemExit('Webcam tidak dapat dibuka. Coba --camera 1 atau tutup aplikasi kamera lain.')
        while True:
            ok, frame = cap.read()
            if not ok:
                status = 'Webcam terputus'
                print(status)
                break
            # Infer on original orientation: training images need not be mirrored.
            result = model.predict(frame, conf=args.confidence, verbose=False)[0]
            labels = [normalize_label(model.names[int(box.cls.item())]) for box in result.boxes]
            # Multiple hands/boxes are ambiguous: require exactly one accepted detection.
            label = labels[0] if len(labels) == 1 else ('ambiguous' if labels else None)
            now = time.monotonic()
            if pending is not None and pending.done():
                try:
                    value = pending.result()
                    if kind == 'poll':
                        snapshot, status = value, 'ESP32 online'
                    else:
                        status = value
                    print(status)
                except BlynkError as error:
                    snapshot, status = {}, str(error)
                    print(status)
                pending = None
                last_poll = now
            event = gate.update(label, now)
            if event:
                if args.dry_run:
                    status = f'DRY RUN: {event}'
                    print(status)
                elif pending is None:
                    pending, kind = pool.submit(client.command, event), 'command'
                    status = 'Mengirim perintah...'
                else:
                    status = 'Blynk sibuk; lepas tangan lalu ulangi gestur'
            if client and pending is None and now - last_poll >= 3:
                pending, kind = pool.submit(client.snapshot), 'poll'
            display = result.plot()
            lines = [f'Gesture: {label or "none / ambiguous"}', status,
                     'Lepas tangan 0.6 detik setelah aksi | Q / Esc: keluar',
                     f'Sistem aktual: {snapshot.get("v6", "?")} | Servo: {snapshot.get("v7", "?")}',
                     '  '.join(f'{name}: {snapshot.get(pin, "?")}' for name, pin in
                               [('C', 'v1'), ('pH', 'v2'), ('gram', 'v4'), ('NTU simulasi', 'v5')]),
                     f'ESP32: {snapshot.get("v8", "?")}']
            for index, line in enumerate(lines):
                cv2.putText(display, line, (12, 26 + index * 26), cv2.FONT_HERSHEY_SIMPLEX,
                            0.5, (0, 255, 255), 1, cv2.LINE_AA)
            cv2.imshow('YOLOv8 Feeding System', display)
            if cv2.waitKey(1) & 0xFF in (27, ord('q')):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        pool.shutdown(wait=True, cancel_futures=True)
        if client:
            client.close()


if __name__ == '__main__':
    main()
