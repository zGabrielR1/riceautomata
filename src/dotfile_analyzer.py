import os
import re
from typing import Dict, List, Tuple
from src.utils import setup_logger

logger = setup_logger()

class DotfileAnalyzer:
    """Handles the analysis and scoring of potential dotfile directories."""
    
    def __init__(self, rules_config=None, verbose=False):
        self.rules_config = rules_config or {}
        self.verbose = verbose
        self.logger = logger
        self._init_scoring_rules()
        
    def _init_scoring_rules(self):
        """Initialize scoring rules with default values."""
        self.name_patterns = {
            r'^\.(config|conf)$': 10,
            r'^\.(vim|emacs|bash|zsh)$': 8,
            r'^\..*rc$': 7,
            r'^\.[A-Za-z0-9-_]+$': 5
        }
        
        self.content_patterns = {
            r'(vim|emacs|bash|zsh)rc': 8,
            r'config\.(yaml|json|toml)': 7,
            r'\.gitconfig': 6,
            r'environment': 5
        }
        
        # Update with custom rules if provided
        if self.rules_config:
            self.name_patterns.update(self.rules_config.get('name_patterns', {}))
            self.content_patterns.update(self.rules_config.get('content_patterns', {}))
            
    def analyze_directory(self, directory: str) -> Dict[str, Dict]:
        """
        Analyze a directory and its contents to identify potential dotfile directories.
        
        Args:
            directory: Path to the directory to analyze
            
        Returns:
            Dict containing analysis results for each subdirectory
        """
        results = {}
        try:
            for root, dirs, files in os.walk(directory):
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    score = self._score_directory(dir_path)
                    metadata = self._collect_metadata(dir_path)
                    
                    if score > 0:
                        results[dir_path] = {
                            'score': score,
                            'metadata': metadata,
                            'confidence': self._calculate_confidence(score, metadata)
                        }
                        
                        if self.verbose:
                            self.logger.debug(f"Directory {dir_path} scored {score} points")
                            
        except Exception as e:
            self.logger.error(f"Error analyzing directory {directory}: {e}")
            
        return results
        
    def _score_directory(self, directory: str) -> float:
        """
        Calculate a score for a directory based on its name and contents.
        
        Args:
            directory: Path to the directory to score
            
        Returns:
            Float score indicating likelihood of being a dotfile directory
        """
        score = 0.0
        
        # Score based on directory name
        dir_name = os.path.basename(directory)
        score += self._score_dir_name(dir_name)
        
        # Score based on contents
        score += self._score_dotfile_content(directory)
        
        return score
        
    def _score_dir_name(self, dir_name: str) -> float:
        """Score a directory name based on patterns."""
        score = 0.0
        for pattern, points in self.name_patterns.items():
            if re.search(pattern, dir_name, re.IGNORECASE):
                score += points
                if self.verbose:
                    self.logger.debug(f"Directory name {dir_name} matched pattern {pattern} (+{points} points)")
        return score
        
    def _score_dotfile_content(self, directory: str) -> float:
        """Score directory contents based on patterns."""
        score = 0.0
        try:
            for root, _, files in os.walk(directory):
                for file_name in files:
                    file_path = os.path.join(root, file_name)
                    
                    # Score based on file name patterns
                    for pattern, points in self.content_patterns.items():
                        if re.search(pattern, file_name, re.IGNORECASE):
                            score += points
                            if self.verbose:
                                self.logger.debug(f"File {file_name} matched pattern {pattern} (+{points} points)")
                            
                    # Score based on file content (first few lines)
                    score += self._analyze_file_content(file_path)
                    
        except Exception as e:
            self.logger.error(f"Error scoring directory contents {directory}: {e}")
            
        return score
        
    def _analyze_file_content(self, file_path: str, max_lines: int = 10) -> float:
        """Analyze the content of a file for dotfile indicators."""
        score = 0.0
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    
                    # Look for common dotfile indicators in content
                    if re.search(r'(export|alias|source|set\s+[-\w]+)', line):
                        score += 2
                    elif re.search(r'(config|settings|preferences)', line, re.IGNORECASE):
                        score += 1
                        
        except Exception as e:
            if self.verbose:
                self.logger.debug(f"Could not analyze file {file_path}: {e}")
                
        return score
        
    def _collect_metadata(self, directory: str) -> Dict:
        """Collect metadata about the directory."""
        try:
            return {
                'file_count': sum(len(files) for _, _, files in os.walk(directory)),
                'total_size': sum(
                    os.path.getsize(os.path.join(root, file))
                    for root, _, files in os.walk(directory)
                    for file in files
                ),
                'last_modified': max(
                    os.path.getmtime(os.path.join(root, file))
                    for root, _, files in os.walk(directory)
                    for file in files
                ) if any(os.walk(directory))[2] else 0,
                'depth': len(os.path.relpath(directory).split(os.sep))
            }
        except Exception as e:
            self.logger.error(f"Error collecting metadata for {directory}: {e}")
            return {}
            
    def _calculate_confidence(self, score: float, metadata: Dict) -> float:
        """Calculate confidence score based on directory score and metadata."""
        confidence = min(score / 100.0, 1.0)  # Base confidence on score
        
        # Adjust confidence based on metadata
        if metadata.get('file_count', 0) > 10:
            confidence *= 1.2
        if metadata.get('depth', 0) > 3:
            confidence *= 0.8
            
        return min(confidence, 1.0)  # Ensure confidence is between 0 and 1
