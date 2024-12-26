class RiceAutomataError(Exception):
    """Base exception class for RiceAutomata."""
    def __init__(self, message: str, details: str = None):
        super().__init__(message)
        self.details = details
    def __str__(self):
        if self.details:
            return f"{super().__str__()}\nDetails: {self.details}"
        return super().__str__()

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
