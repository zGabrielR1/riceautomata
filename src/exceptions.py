class RiceAutomataError(Exception):
    """Base exception class for RiceAutomata."""
    pass

class ConfigurationError(RiceAutomataError):
    """Raised when there's an error in configuration."""
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
    """Raised when rollback operation fails."""
    pass

class TemplateRenderingError(RiceAutomataError):
    """Raised when there's an error in template rendering."""
    pass

class ScriptExecutionError(RiceAutomataError):
    """Raised when script execution fails."""
    pass
