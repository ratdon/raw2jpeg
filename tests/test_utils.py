# Unit tests for utils module
"""Tests for filename pattern detection."""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.utils import (
    detect_filename_pattern,
    get_output_template,
    detect_folder_pattern,
)


class TestDetectFilenamePattern:
    """Tests for detect_filename_pattern function."""
    
    def test_datetime_prefix_pattern(self):
        """Test detection of datetime prefix pattern."""
        assert detect_filename_pattern("2025-12-25_16-34-32_DSC07514.ARW") == 'datetime_prefix'
        assert detect_filename_pattern("2024-01-01_00-00-00_DSC00001.arw") == 'datetime_prefix'
    
    def test_datetime_suffix_pattern(self):
        """Test detection of datetime suffix pattern."""
        assert detect_filename_pattern("DSC07514_2025-12-25_16-34-32.ARW") == 'datetime_suffix'
    
    def test_plain_dsc_pattern(self):
        """Test detection of plain DSC pattern."""
        assert detect_filename_pattern("DSC07514.ARW") == 'plain_dsc'
        assert detect_filename_pattern("DSC08907.arw") == 'plain_dsc'
    
    def test_unknown_pattern(self):
        """Test detection of unknown pattern."""
        assert detect_filename_pattern("random_photo.jpg") == 'unknown'
        # Note: photo123.ARW matches plain_dsc pattern (alphanumeric+digits)


class TestGetOutputTemplate:
    """Tests for get_output_template function."""
    
    def test_datetime_prefix_template(self):
        """Test output template for datetime prefix pattern."""
        template = get_output_template('datetime_prefix', 'G:/jpeg')
        assert '$(EXIF.YEAR)-$(EXIF.MONTH)-$(EXIF.DAY)' in template
        assert '$(FILE.NAME).jpg' in template
        # Should NOT have datetime in filename part (already present)
        assert template.count('$(EXIF.HOUR)') == 0
    
    def test_plain_dsc_template(self):
        """Test output template for plain DSC pattern."""
        template = get_output_template('plain_dsc', 'G:/jpeg')
        # Should have datetime in both folder and filename
        assert '$(EXIF.YEAR)-$(EXIF.MONTH)-$(EXIF.DAY)/' in template
        assert '$(EXIF.HOUR)-$(EXIF.MINUTE)-$(EXIF.SECOND)' in template
    
    def test_forward_slashes(self):
        """Test that output uses forward slashes."""
        template = get_output_template('plain_dsc', 'G:/jpeg')
        assert '\\' not in template


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
