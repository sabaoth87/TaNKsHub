import re
from dataclasses import dataclass
from typing import Optional
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@dataclass
class MediaInfo:
    title: str
    year: Optional[str] = None
    season: Optional[str] = None
    episode: Optional[str] = None

class FilenameParser:
    def __init__(self):
        # Patterns for different filename formats
        self.movie_patterns = [
            # Pattern: Movie.Name.2024.1080p...
            r'^((?:[A-Za-z0-9.]+[. ])*?)(?:[\[(]?(\d{4})[\])]?)',
            # Pattern: Movie.Name.(2024)...
            r'^((?:[A-Za-z0-9.]+[. ])*?)\((\d{4})\)',
            r'^(.*?)[\.\s](\d{4})[\.\s]',  # More general pattern: anything followed by 4 digits
            r'^(.*?)[_\-\.\s]\((\d{4})\)',  # Title followed by (year)
            r'^(.*?)[\.\s]\[(\d{4})\]'      # Title followed by [year]
        ]
        
        self.tv_patterns = [
            # Pattern: Show.Name.S01E02...
            r'^((?:[A-Za-z0-9.]+[. ])*?)S(\d{1,2})E(\d{1,2})',
            # Pattern: Show.Name.1x02...
            r'^((?:[A-Za-z0-9.]+[. ])*?)(\d{1,2})x(\d{1,2})',
        ]

    def clean_title(self, title: str) -> str:
        """Clean up title by replacing dots/underscores with spaces and proper capitalization"""
        # Replace dots and underscores with spaces
        title = re.sub(r'[._]', ' ', title)
        # Remove any remaining unwanted characters
        title = re.sub(r'[^\w\s-]', '', title)
        # Proper title case
        title = ' '.join(word.capitalize() for word in title.split())
        return title.strip()

    def parse_filename(self, filename: str) -> MediaInfo:
        """Parse filename and extract media information"""
        logger.debug(f"Parsing filename: {filename}")
        
        # Try TV show patterns first
        for pattern in self.tv_patterns:
            match = re.match(pattern, filename)
            if match:
                logger.debug(f"Matched TV pattern: {pattern}")
                title = self.clean_title(match.group(1))
                return MediaInfo(
                    title=title,
                    season=str(int(match.group(2))),  # Remove leading zeros
                    episode=str(int(match.group(3)))
                )
        
        # Try movie patterns
        for pattern in self.movie_patterns:
            match = re.match(pattern, filename)
            if match:
                logger.debug(f"Matched movie pattern: {pattern}")
                title = self.clean_title(match.group(1))
                return MediaInfo(
                    title=title,
                    year=match.group(2)
                )
        
        # If no pattern matches, just clean the filename
        logger.debug("No pattern matched, using clean title only")
        return MediaInfo(title=self.clean_title(filename))

    def generate_filename(self, media_info: MediaInfo) -> str:
        """Generate clean filename from MediaInfo"""
        logger.debug(f"Generating filename from: {media_info}")
        
        if media_info.season and media_info.episode:
            # TV Show format: "Show Name - S01E02"
            result = f"{media_info.title} - S{media_info.season.zfill(2)}E{media_info.episode.zfill(2)}"
        elif media_info.year:
            # Movie format: "Movie Name (2024)"
            result = f"{media_info.title} ({media_info.year})"
        else:
            # Just the clean title
            result = media_info.title
            
        logger.debug(f"Generated filename: {result}")
        return result


def test_filename_parser():
    parser = FilenameParser()
    
    test_files = [
        "Movie.Name.2021.1080p.mkv",
        "Movie.Name.(2021).mkv",
        "TV.Show.S01E02.mkv",
        "TV.Show.1x02.mkv",
        "Just.A.Random.Filename.mkv",
        "Godzilla.vs.Kong.2021.1080p.WEBRip.x264-RARBG.mp4",
        "Hamilton.2020.720p.WEBRip.x264.AAC-[YTS.MX].mp4",
        "Greys.Anatomy.S17E03.HDTV.x264-PHOENiX.mkv"
    ]
    
    print("\nTesting FilenameParser with sample files:")
    print("-" * 60)
    
    for test_file in test_files:
        print(f"File: {test_file}")
        
        # Get file stem (without extension)
        stem = test_file.rsplit('.', 1)[0]
        
        # Parse the filename
        media_info = parser.parse_filename(stem)
        print(f"  Parsed as: {media_info}")
        
        # Generate new filename
        new_name = parser.generate_filename(media_info)
        print(f"  New name: {new_name}")
        
        # Add back the extension
        extension = test_file.rsplit('.', 1)[1] if '.' in test_file else ''
        full_new_name = f"{new_name}.{extension}" if extension else new_name
        print(f"  Final: {full_new_name}")
        
        if test_file.rsplit('.', 1)[0] == new_name:
            print("  ⚠️ WARNING: Name unchanged!")
        print()


if __name__ == "__main__":
    test_filename_parser()
