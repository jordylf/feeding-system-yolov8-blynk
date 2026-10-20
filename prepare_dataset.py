"""Extract Roboflow YOLO archive and write portable, corrected split paths."""
import argparse
from collections import Counter
from pathlib import Path
import zipfile

import yaml

ROOT = Path(__file__).resolve().parent


def detection_label(line: str) -> tuple[str, bool]:
    values = line.split()
    if not values:
        return '', False
    if values[0] not in ('0', '1'):
        raise ValueError('Class ID harus 0 atau 1.')
    coords = [float(x) for x in values[1:]]
    if not all(0 <= x <= 1 for x in coords):
        raise ValueError('Koordinat harus finite dan berada di rentang 0..1.')
    converted = len(values) != 5
    if converted:
        if len(coords) < 6 or len(coords) % 2:
            raise ValueError('Polygon harus memiliki minimal tiga pasangan x,y.')
        xs, ys = coords[::2], coords[1::2]
        coords = [(min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2,
                  max(xs) - min(xs), max(ys) - min(ys)]
    if min(coords[2:]) <= 0:
        raise ValueError('Bounding box memiliki luas nol.')
    return values[0] + ' ' + ' '.join(f'{value:.8f}' for value in coords), converted


def prepare(archive: Path, destination: Path):
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as source:
        for entry in source.infolist():
            target = (destination / entry.filename).resolve()
            if not target.is_relative_to(destination):
                raise ValueError('ZIP mengandung path di luar folder dataset.')
        source.extractall(destination)
    metadata = yaml.safe_load((destination / 'data.yaml').read_text(encoding='utf-8'))
    if metadata.get('names') != ['finger up', 'palm open'] or metadata.get('nc') != 2:
        raise ValueError('Dataset harus memiliki kelas 0=finger up dan 1=palm open.')
    summary = {}
    for split in ('train', 'valid', 'test'):
        images = list((destination / split / 'images').glob('*'))
        if not images:
            raise ValueError(f'Split {split} tidak memiliki gambar.')
        counts = Counter()
        converted_count = 0
        for image in images:
            label = destination / split / 'labels' / f'{image.stem}.txt'
            if not label.exists():
                raise ValueError(f'Label hilang: {label.name}')
            normalized = []
            for line in label.read_text().splitlines():
                try:
                    output, converted = detection_label(line)
                except ValueError as error:
                    raise ValueError(f'{label.name}: {error}') from error
                if output:
                    normalized.append(output)
                    counts[int(output.split()[0])] += 1
                    converted_count += int(converted)
            label.write_text('\n'.join(normalized) + ('\n' if normalized else ''), encoding='utf-8')
        summary[split] = {'images': len(images), 'objects': dict(counts), 'polygons_to_boxes': converted_count}
    metadata.update(path=destination.as_posix(), train='train/images', val='valid/images', test='test/images')
    data_file = destination / 'data.yaml'
    data_file.write_text(yaml.safe_dump(metadata, sort_keys=False), encoding='utf-8')
    print(yaml.safe_dump(summary, sort_keys=False))
    return data_file


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--zip', type=Path, default=ROOT / 'feeding system.v7i.yolov8.zip')
    parser.add_argument('--output', type=Path, default=ROOT / 'datasets' / 'feeding')
    args = parser.parse_args()
    print('Dataset YAML:', prepare(args.zip, args.output))
