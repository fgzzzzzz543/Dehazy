import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys

ERROR_COUNTERS = (
    'bad_captures', 'failed_frames', 'protocol_errors', 'axi_errors',
    'frontend_errors', 'display_errors', 'frontend_drops', 'frontend_underflows',
)
COUNTERS = (
    'captured_good', 'completed_frames', 'displayed_new_frames',
    'repeated_frames', 'frontend_capture_ends', 'rejected_captures',
) + ERROR_COUNTERS
TIMING_COLUMNS = (
    'pipeline_ticks_start_us', 'pipeline_ticks_end_us',
    'display_ticks_start_us', 'display_ticks_end_us',
)
OPTIONAL_COLUMNS = (
    'sample_index', 'first_display_cycle', 'last_display_cycle',
    'run_enable', 'state_status', 'frontend_status',
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def read_samples(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        require(len(fields) == len(set(fields)), 'Duplicate CSV column names')
        missing = set(COUNTERS + TIMING_COLUMNS) - set(fields)
        require(not missing, 'Not the supported V5 sample schema; missing: ' + ', '.join(sorted(missing)))
        columns = list(COUNTERS + TIMING_COLUMNS) + [name for name in OPTIONAL_COLUMNS if name in fields]
        rows = []
        for line_number, raw in enumerate(reader, start=2):
            require(None not in raw, 'Too many CSV fields at line ' + str(line_number))
            try:
                rows.append({name: int(raw[name]) for name in columns})
            except (TypeError, ValueError) as error:
                raise ValueError('Invalid integer at CSV line ' + str(line_number)) from error
    return rows


def elapsed(first, last, prefix):
    return ((last[prefix + '_start_us'] + last[prefix + '_end_us']) -
            (first[prefix + '_start_us'] + first[prefix + '_end_us'])) / 2_000_000


def audit_samples(rows, clock_hz=None):
    require(len(rows) >= 2, 'At least two snapshots are required')
    if clock_hz is not None:
        require(math.isfinite(clock_hz) and clock_hz > 0, 'Clock frequency must be finite and positive')
        require(all('last_display_cycle' in row for row in rows), 'Hardware clock supplied without last_display_cycle')
    for row in rows:
        require(all(name in row for name in COUNTERS + TIMING_COLUMNS), 'Missing required snapshot field')
        require(all(row[name] >= 0 for name in COUNTERS + TIMING_COLUMNS), 'Negative counter or monotonic timestamp')
        for prefix in ['display_ticks', 'pipeline_ticks']:
            require(row[prefix + '_end_us'] >= row[prefix + '_start_us'], 'Read bracket end precedes start')
    for previous, current in zip(rows, rows[1:]):
        for name in COUNTERS:
            require(current[name] >= previous[name], 'Counter decreased; do not silently infer rollover: ' + name)
        for prefix in ['display_ticks', 'pipeline_ticks']:
            require(elapsed(previous, current, prefix) > 0, 'Nonpositive snapshot interval: ' + prefix)
        if 'sample_index' in previous and 'sample_index' in current:
            require(current['sample_index'] > previous['sample_index'], 'Sample indices are not strictly increasing')
        if 'last_display_cycle' in previous and 'last_display_cycle' in current:
            require(current['last_display_cycle'] >= previous['last_display_cycle'], 'Hardware timestamp decreased')
    if all('first_display_cycle' in row for row in rows):
        require(len({row['first_display_cycle'] for row in rows}) == 1, 'Display time origin changed; investigate restart')
    first, last = rows[0], rows[-1]
    display_seconds = elapsed(first, last, 'display_ticks')
    pipeline_seconds = elapsed(first, last, 'pipeline_ticks')
    delta = {name: last[name] - first[name] for name in COUNTERS}
    counters = {name: {'start': first[name], 'end': last[name], 'delta': delta[name]} for name in COUNTERS}
    rates = {
        'new_frame_display_fps': delta['displayed_new_frames'] / display_seconds,
        'processing_completed_fps': delta['completed_frames'] / pipeline_seconds,
        'good_capture_fps': delta['captured_good'] / pipeline_seconds,
        'frontend_frame_end_rate_hz': delta['frontend_capture_ends'] / display_seconds,
        'display_presentation_rate_including_repeats_hz': (delta['displayed_new_frames'] + delta['repeated_frames']) / display_seconds,
        'repeated_presentation_rate_hz': delta['repeated_frames'] / display_seconds,
    }
    hardware_seconds = None
    if clock_hz is not None:
        hardware_seconds = (last['last_display_cycle'] - first['last_display_cycle']) / clock_hz
        require(hardware_seconds > 0, 'Hardware event span is nonpositive; do not substitute a default denominator')
        rates['hardware_new_frame_span_fps_reference'] = delta['displayed_new_frames'] / hardware_seconds
    total_capture_requests = delta['captured_good'] + delta['bad_captures'] + delta['rejected_captures']
    reject_fraction = delta['rejected_captures'] / total_capture_requests if total_capture_requests else None
    accounting_difference = delta['frontend_capture_ends'] - total_capture_requests
    errors_zero = all(row[name] == 0 for row in rows for name in ERROR_COUNTERS)
    controls_valid = None
    if all(all(name in row for name in ['run_enable', 'state_status', 'frontend_status']) for row in rows):
        controls_valid = all(row['run_enable'] == 1 and row['state_status'] & 0x31 == 0x31 and row['frontend_status'] & 3 == 3 for row in rows)
    intervals = []
    for previous, current in zip(rows, rows[1:]):
        duration = elapsed(previous, current, 'display_ticks')
        new_frames = current['displayed_new_frames'] - previous['displayed_new_frames']
        intervals.append({'seconds': duration, 'new_frames': new_frames, 'new_frame_display_fps': new_frames / duration})
    observations = []
    if delta['rejected_captures']:
        observations.append('Admission rejections are nonzero; do not claim zero frame loss')
    if not errors_zero:
        observations.append('At least one sampled error counter is nonzero')
    if controls_valid is False:
        observations.append('At least one sampled V5 run/configuration/camera/PLL state is invalid')
    if accounting_difference:
        observations.append('Capture accounting does not reconcile; investigate definitions and snapshot atomicity')
    if total_capture_requests == 0:
        observations.append('No capture requests in the window; rejection fraction is undefined, not zero')
    if any(interval['new_frames'] == 0 for interval in intervals):
        observations.append('At least one interval contains no new displayed frames; the full window was retained')
    return {
        'state': 'AUDIT_COMPLETE',
        'scope': 'OFFLINE_RECOMPUTATION_ONLY',
        'operational_acceptance': 'NOT_ASSESSED',
        'board_access': False,
        'window': {'samples': len(rows), 'intervals': len(intervals),
                   'new_frame_counter_window_seconds': display_seconds,
                   'pipeline_counter_window_seconds': pipeline_seconds,
                   'clock_hz_explicitly_supplied': clock_hz,
                   'hardware_last_new_frame_span_seconds': hardware_seconds},
        'rates': rates,
        'counters': counters,
        'input_admission_reject_fraction': reject_fraction,
        'capture_accounting_difference_frontend_minus_accepted_bad_rejected': accounting_difference,
        'checks': {'all_sampled_error_counters_zero': errors_zero,
                   'no_new_errors_or_underflows': all(delta[name] == 0 for name in ERROR_COUNTERS),
                   'run_configuration_camera_init_and_pll_valid_in_all_samples': controls_valid,
                   'counter_resets_or_decreases_detected': False},
        'new_frame_fps_subwindow_min': min(interval['new_frame_display_fps'] for interval in intervals),
        'new_frame_fps_subwindow_max': max(interval['new_frame_display_fps'] for interval in intervals),
        'intervals': intervals,
        'observations': observations,
        'reference_comparison': {'state': 'NOT_REQUESTED'},
        'image_identity_check': 'NOT_REQUESTED',
    }


def near(actual, expected, name):
    if actual is None or expected is None:
        require(actual is expected, 'Reference mismatch: ' + name)
    else:
        require(math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10), 'Reference mismatch: ' + name)


def compare_reference(result, reference, local_boot_sha256=None):
    for name in ['samples', 'new_frame_counter_window_seconds', 'pipeline_counter_window_seconds']:
        near(result['window'][name], reference['window'][name], 'window.' + name)
    for name, value in result['rates'].items():
        near(value, reference['rates'][name], 'rates.' + name)
    for name, item in result['counters'].items():
        for field in ['start', 'end', 'delta']:
            require(item[field] == reference['counters'][name][field], 'Reference counter mismatch: ' + name + '.' + field)
    for name in ['input_admission_reject_fraction', 'capture_accounting_difference_frontend_minus_accepted_bad_rejected', 'new_frame_fps_subwindow_min', 'new_frame_fps_subwindow_max']:
        near(result[name], reference[name], name)
    if local_boot_sha256 is not None:
        require(local_boot_sha256 == reference['image_sha256'], 'Local BOOT file differs from reference image hash')
        result['image_identity_check'] = 'LOCAL_FILE_MATCHES_REFERENCE_ONLY_NOT_LIVE_BOARD'
    result['reference_comparison'] = {
        'state': 'MATCH_FOR_COMPARED_FIELDS',
        'rate_fields_compared': sorted(result['rates']),
        'reference_rate_fields_not_compared': sorted(set(reference['rates']) - set(result['rates'])),
        'counters_compared': sorted(result['counters']),
        'reference_counter_fields_not_compared': sorted(set(reference['counters']) - set(result['counters'])),
    }


def main():
    parser = argparse.ArgumentParser(description='Offline V5 camera-runtime CSV audit. No board or network access; no files overwritten.')
    parser.add_argument('--samples', required=True, type=Path)
    parser.add_argument('--reference-result', type=Path)
    parser.add_argument('--clock-hz', type=float)
    parser.add_argument('--boot-image', type=Path)
    parser.add_argument('--out', type=Path, help='Optional new output file; defaults to stdout only')
    args = parser.parse_args()
    try:
        if args.out:
            require(not args.out.exists(), 'Output already exists; choose a new result file')
        rows = read_samples(args.samples)
        result = audit_samples(rows, args.clock_hz)
        result['input_samples'] = {'path': str(args.samples.resolve()), 'sha256': digest(args.samples)}
        boot_hash = digest(args.boot_image) if args.boot_image else None
        if boot_hash is not None:
            result['local_boot_sha256'] = boot_hash
            result['image_identity_check'] = 'LOCAL_HASH_ONLY_NOT_LIVE_BOARD'
        if args.reference_result:
            reference = json.loads(args.reference_result.read_text(encoding='utf-8-sig'))
            compare_reference(result, reference, boot_hash)
            result['reference_result'] = {'path': str(args.reference_result.resolve()), 'sha256': digest(args.reference_result)}
        text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open('x', encoding='utf-8') as stream:
                stream.write(text + '\n')
            print(json.dumps({'state': result['state'], 'out': str(args.out.resolve()),
                              'new_frame_display_fps': result['rates']['new_frame_display_fps'],
                              'observations': result['observations'], 'board_access': False}, ensure_ascii=False))
        else:
            print(text)
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'state': 'AUDIT_FAILED', 'error': str(error), 'board_access': False}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
