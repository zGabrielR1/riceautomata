# dotfilemanager/exceptions.py

class RiceAutomataError(Exception):
    """Base exception for DotfileManager errors."""
    pass

class ConfigurationError(RiceAutomataError):
    """Raised when there is a configuration error."""
    pass

class GitOperationError(RiceAutomataError):
    """Raised when a git operation fails."""
    pass

class FileOperationError(RiceAutomataError):
    """Raised when a file operation fails."""
    pass

class ValidationError(RiceAutomataError):
    """Raised when validation fails."""
    pass

class RollbackError(RiceAutomataError):
    """Raised when a rollback operation fails."""
    pass

class TemplateRenderingError(RiceAutomataError):
    """Raised when template rendering fails."""
    pass

class ScriptExecutionError(RiceAutomataError):
    """Raised when script execution fails."""
    pass

class PackageManagerError(RiceAutomataError):
    """Raised when package manager operations fail."""
    pass

class OSManagerError(RiceAutomataError):
    """Raised when OS-specific operations fail."""
    pass

class BackupError(RiceAutomataError):
    """Raised when backup operations fail."""
    pass