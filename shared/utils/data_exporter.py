"""
Data Exporter - Export scraped data to various formats
"""

import json
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class DataExporter:
    """
    Export data to JSON, CSV, Excel, and other formats

    Example:
        exporter = DataExporter()
        exporter.to_json(data, "output.json")
        exporter.to_csv(data, "output.csv")
        exporter.to_excel(data, "output.xlsx")
    """

    @staticmethod
    def to_json(
        data: List[Dict[str, Any]] | Dict[str, Any],
        filepath: str | Path,
        indent: int = 2,
        ensure_ascii: bool = False
    ) -> None:
        """
        Export data to JSON file

        Args:
            data: Data to export
            filepath: Output file path
            indent: JSON indentation (None for compact)
            ensure_ascii: If True, escape non-ASCII characters
        """
        try:
            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii, default=str)

            logger.info(f"Data exported to JSON: {filepath}")

        except Exception as e:
            logger.error(f"Failed to export to JSON: {e}")
            raise

    @staticmethod
    def to_csv(
        data: List[Dict[str, Any]],
        filepath: str | Path,
        flatten: bool = True,
        delimiter: str = ','
    ) -> None:
        """
        Export data to CSV file

        Args:
            data: List of dictionaries to export
            filepath: Output file path
            flatten: If True, flatten nested dictionaries
            delimiter: CSV delimiter character
        """
        try:
            if not data:
                logger.warning("No data to export to CSV")
                return

            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)

            # Flatten data if requested
            if flatten:
                data = DataExporter._flatten_data(data)

            # Get all unique keys from all records
            fieldnames = set()
            for record in data:
                fieldnames.update(record.keys())
            fieldnames = sorted(fieldnames)

            with open(filepath, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter)
                writer.writeheader()
                writer.writerows(data)

            logger.info(f"Data exported to CSV: {filepath}")

        except Exception as e:
            logger.error(f"Failed to export to CSV: {e}")
            raise

    @staticmethod
    def to_excel(
        data: List[Dict[str, Any]] | Dict[str, List[Dict[str, Any]]],
        filepath: str | Path,
        sheet_name: str = 'Data'
    ) -> None:
        """
        Export data to Excel file

        Args:
            data: Data to export (single list or dict of sheet_name -> data)
            filepath: Output file path
            sheet_name: Sheet name (only used if data is a list)
        """
        try:
            import pandas as pd

            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)

            if isinstance(data, list):
                # Single sheet
                df = pd.DataFrame(data)
                df.to_excel(filepath, sheet_name=sheet_name, index=False)

            elif isinstance(data, dict):
                # Multiple sheets
                with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                    for sheet, records in data.items():
                        df = pd.DataFrame(records)
                        df.to_excel(writer, sheet_name=sheet, index=False)

            logger.info(f"Data exported to Excel: {filepath}")

        except ImportError:
            logger.error("pandas and openpyxl are required for Excel export. Install with: pip install pandas openpyxl")
            raise
        except Exception as e:
            logger.error(f"Failed to export to Excel: {e}")
            raise

    @staticmethod
    def to_jsonl(
        data: List[Dict[str, Any]],
        filepath: str | Path,
        ensure_ascii: bool = False
    ) -> None:
        """
        Export data to JSON Lines format (one JSON object per line)

        Args:
            data: List of dictionaries to export
            filepath: Output file path
            ensure_ascii: If True, escape non-ASCII characters
        """
        try:
            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, 'w', encoding='utf-8') as f:
                for record in data:
                    json.dump(record, f, ensure_ascii=ensure_ascii, default=str)
                    f.write('\n')

            logger.info(f"Data exported to JSONL: {filepath}")

        except Exception as e:
            logger.error(f"Failed to export to JSONL: {e}")
            raise

    @staticmethod
    def _flatten_data(data: List[Dict[str, Any]], sep: str = '_') -> List[Dict[str, Any]]:
        """
        Flatten nested dictionaries and convert lists to JSON strings

        Args:
            data: List of dictionaries to flatten
            sep: Separator for nested keys

        Returns:
            List of flattened dictionaries
        """
        flattened_data = []

        for record in data:
            flattened_record = DataExporter._flatten_dict(record, sep=sep)
            flattened_data.append(flattened_record)

        return flattened_data

    @staticmethod
    def _flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '_') -> Dict[str, Any]:
        """
        Recursively flatten a nested dictionary

        Args:
            d: Dictionary to flatten
            parent_key: Parent key for nested items
            sep: Separator for nested keys

        Returns:
            Flattened dictionary
        """
        items = {}

        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k

            if isinstance(v, dict):
                # Recursively flatten nested dictionaries
                items.update(DataExporter._flatten_dict(v, new_key, sep))

            elif isinstance(v, list):
                if v and isinstance(v[0], dict):
                    # Convert list of dicts to JSON string
                    items[new_key] = json.dumps(v, default=str)
                else:
                    # Convert simple lists to comma-separated string
                    items[new_key] = ', '.join(str(item) for item in v)

            else:
                items[new_key] = v

        return items

    @staticmethod
    def auto_export(
        data: List[Dict[str, Any]],
        base_filename: str,
        formats: List[str] = ['json', 'csv'],
        output_dir: str = 'output'
    ) -> Dict[str, Path]:
        """
        Export data to multiple formats automatically

        Args:
            data: Data to export
            base_filename: Base filename without extension
            formats: List of formats to export ('json', 'csv', 'excel', 'jsonl')
            output_dir: Output directory

        Returns:
            Dictionary of format -> filepath
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        exported_files = {}
        exporter = DataExporter()

        for fmt in formats:
            if fmt == 'json':
                filepath = output_dir / f"{base_filename}.json"
                exporter.to_json(data, filepath)
                exported_files['json'] = filepath

            elif fmt == 'csv':
                filepath = output_dir / f"{base_filename}.csv"
                exporter.to_csv(data, filepath)
                exported_files['csv'] = filepath

            elif fmt == 'excel':
                filepath = output_dir / f"{base_filename}.xlsx"
                exporter.to_excel(data, filepath)
                exported_files['excel'] = filepath

            elif fmt == 'jsonl':
                filepath = output_dir / f"{base_filename}.jsonl"
                exporter.to_jsonl(data, filepath)
                exported_files['jsonl'] = filepath

        return exported_files
