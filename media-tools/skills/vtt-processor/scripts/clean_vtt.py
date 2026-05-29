#!/usr/bin/env python3
"""
VTT Transcript Cleaner for Talent Hiring

Converts verbose WebVTT files into clean, token-efficient transcripts.
Removes timestamps, UUIDs, and metadata while preserving speaker attribution.

Usage:
    python clean_vtt.py input.vtt                    # Output to stdout
    python clean_vtt.py input.vtt -o output.txt     # Output to file
    python clean_vtt.py input.vtt --in-place        # Replace .vtt with .txt

Examples:
    python clean_vtt.py 2025-01-07-screening.vtt -o 2025-01-07-screening.txt
    python clean_vtt.py transcripts/*.vtt --in-place
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Iterator, Optional


def parse_vtt_blocks(content: str) -> Iterator[tuple[Optional[str], str]]:
    """
    Parse VTT content into (speaker, text) tuples.

    Handles:
    - Speaker tags: <v Speaker Name>text</v>
    - Multi-line text within a single cue
    - Cues without speaker attribution
    """
    lines = content.split('\n')
    current_text_lines: list[str] = []
    current_speaker: Optional[str] = None
    in_cue = False

    # Patterns
    timestamp_pattern = re.compile(r'^\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}')
    uuid_pattern = re.compile(r'^[a-f0-9-]{36}/\d+-\d+$')
    speaker_tag_pattern = re.compile(r'<v\s+([^>]+)>(.*?)(?:</v>)?$', re.DOTALL)
    closing_tag_pattern = re.compile(r'(.*?)</v>$')

    for line in lines:
        line = line.rstrip()

        # Skip WEBVTT header
        if line == 'WEBVTT':
            continue

        # Skip UUID identifiers
        if uuid_pattern.match(line):
            continue

        # Skip timestamp lines but mark that we're in a cue
        if timestamp_pattern.match(line):
            # Yield previous cue if exists
            if current_text_lines:
                text = ' '.join(current_text_lines).strip()
                if text:
                    yield (current_speaker, text)
                current_text_lines = []
                current_speaker = None
            in_cue = True
            continue

        # Empty line ends a cue
        if not line:
            if current_text_lines:
                text = ' '.join(current_text_lines).strip()
                if text:
                    yield (current_speaker, text)
                current_text_lines = []
                current_speaker = None
            in_cue = False
            continue

        # Process text content
        if in_cue:
            # Check for speaker tag at start of line
            speaker_match = speaker_tag_pattern.match(line)
            if speaker_match:
                current_speaker = speaker_match.group(1).strip()
                text_content = speaker_match.group(2).strip()
                if text_content:
                    current_text_lines.append(text_content)
            else:
                # Check for closing tag
                closing_match = closing_tag_pattern.match(line)
                if closing_match:
                    text_content = closing_match.group(1).strip()
                    if text_content:
                        current_text_lines.append(text_content)
                else:
                    # Regular text line (continuation or no speaker)
                    if line.strip():
                        current_text_lines.append(line.strip())

    # Yield final cue if exists
    if current_text_lines:
        text = ' '.join(current_text_lines).strip()
        if text:
            yield (current_speaker, text)


def merge_consecutive_speakers(blocks: Iterator[tuple[Optional[str], str]]) -> Iterator[tuple[Optional[str], str]]:
    """
    Merge consecutive blocks from the same speaker into single entries.
    """
    current_speaker: Optional[str] = None
    current_texts: list[str] = []

    for speaker, text in blocks:
        if speaker == current_speaker:
            # Same speaker, accumulate text
            current_texts.append(text)
        else:
            # Different speaker, yield previous and start new
            if current_texts:
                yield (current_speaker, ' '.join(current_texts))
            current_speaker = speaker
            current_texts = [text]

    # Yield final accumulated text
    if current_texts:
        yield (current_speaker, ' '.join(current_texts))


def format_transcript(blocks: Iterator[tuple[Optional[str], str]], unknown_speaker: str = "Unknown") -> str:
    """
    Format merged blocks into clean transcript text.

    Output format:
        Speaker Name: Their transcribed text goes here.

        Another Speaker: Their response follows.
    """
    output_lines: list[str] = []

    for speaker, text in blocks:
        speaker_name = speaker if speaker else unknown_speaker
        output_lines.append(f"{speaker_name}: {text}")

    return '\n\n'.join(output_lines)


def clean_vtt(content: str, unknown_speaker: str = "Unknown") -> str:
    """
    Main function to clean VTT content.

    Args:
        content: Raw VTT file content
        unknown_speaker: Label for cues without speaker attribution

    Returns:
        Cleaned transcript as formatted string
    """
    blocks = parse_vtt_blocks(content)
    merged = merge_consecutive_speakers(blocks)
    return format_transcript(merged, unknown_speaker)


def process_file(input_path: Path, output_path: Optional[Path] = None, unknown_speaker: str = "Unknown") -> str:
    """
    Process a single VTT file.

    Args:
        input_path: Path to input VTT file
        output_path: Optional path for output (None = return string only)
        unknown_speaker: Label for cues without speaker attribution

    Returns:
        Cleaned transcript content
    """
    content = input_path.read_text(encoding='utf-8')
    cleaned = clean_vtt(content, unknown_speaker)

    if output_path:
        output_path.write_text(cleaned, encoding='utf-8')

    return cleaned


def main():
    parser = argparse.ArgumentParser(
        description="Clean VTT transcripts for better token efficiency",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s interview.vtt                     # Print to stdout
    %(prog)s interview.vtt -o clean.txt       # Save to file
    %(prog)s interview.vtt --in-place         # Create interview.txt alongside
    %(prog)s transcripts/*.vtt --in-place     # Batch process multiple files
        """
    )

    parser.add_argument(
        'input_files',
        nargs='+',
        type=Path,
        help='VTT file(s) to process'
    )

    parser.add_argument(
        '-o', '--output',
        type=Path,
        help='Output file path (only valid with single input file)'
    )

    parser.add_argument(
        '--in-place',
        action='store_true',
        help='Create .txt file alongside each input .vtt file'
    )

    parser.add_argument(
        '--unknown-speaker',
        default='Unknown',
        help='Label for cues without speaker attribution (default: Unknown)'
    )

    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show token reduction statistics'
    )

    args = parser.parse_args()

    # Validate arguments
    if args.output and len(args.input_files) > 1:
        parser.error("--output can only be used with a single input file")

    if args.output and args.in_place:
        parser.error("--output and --in-place are mutually exclusive")

    for input_path in args.input_files:
        if not input_path.exists():
            print(f"Error: File not found: {input_path}", file=sys.stderr)
            continue

        if not input_path.suffix.lower() == '.vtt':
            print(f"Warning: {input_path} does not have .vtt extension", file=sys.stderr)

        # Determine output path
        if args.output:
            output_path = args.output
        elif args.in_place:
            output_path = input_path.with_suffix('.txt')
        else:
            output_path = None

        # Process file
        original_size = input_path.stat().st_size
        cleaned = process_file(input_path, output_path, args.unknown_speaker)

        # Output handling
        if output_path:
            if args.stats:
                new_size = output_path.stat().st_size
                reduction = (1 - new_size / original_size) * 100
                print(f"{input_path.name}: {original_size:,} -> {new_size:,} bytes ({reduction:.1f}% reduction)")
            else:
                print(f"Created: {output_path}")
        else:
            # Print to stdout
            print(cleaned)
            if args.stats:
                new_size = len(cleaned.encode('utf-8'))
                reduction = (1 - new_size / original_size) * 100
                print(f"\n---\nStats: {original_size:,} -> {new_size:,} bytes ({reduction:.1f}% reduction)", file=sys.stderr)


if __name__ == "__main__":
    main()
