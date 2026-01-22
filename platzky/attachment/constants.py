"""Attachment size limits and related constants."""

# Default maximum attachment size: 10MB
DEFAULT_MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024

# Blocked file extensions - dangerous executable and script formats
BLOCKED_EXTENSIONS: frozenset[str] = frozenset(
    {
        # Windows executables
        "exe",
        "dll",
        "scr",
        "msi",
        "com",
        "pif",
        # Windows scripts
        "bat",
        "cmd",
        "vbs",
        "vbe",
        "js",
        "jse",
        "ws",
        "wsf",
        "wsc",
        "wsh",
        "ps1",
        "psm1",
        "psd1",
        # Shortcuts and links
        "lnk",
        "url",
        "hta",
        # macOS executables
        "app",
        "dmg",
        "pkg",
        # Linux packages
        "deb",
        "rpm",
        "appimage",
        # Shell scripts
        "sh",
        "bash",
        "zsh",
        "ksh",
        "csh",
        # Scripting languages
        "py",
        "pyc",
        "pyo",
        "pyw",
        "rb",
        "pl",
        "php",
        "php3",
        "php4",
        "php5",
        "phtml",
        # Java
        "jar",
        "class",
        "war",
        # Other dangerous formats
        "reg",  # Windows registry
        "inf",  # Windows setup information
        "scf",  # Windows Explorer command
        "cpl",  # Control panel extension
        "msc",  # Microsoft Management Console
        "gadget",  # Windows gadget
    }
)


class BlockedExtensionError(ValueError):
    """Raised when attachment has a blocked file extension."""

    def __init__(self, filename: str, extension: str) -> None:
        self.filename = filename
        self.extension = extension
        message = (
            f"Attachment '{filename}' has blocked extension '.{extension}'. "
            f"Executable and script file types are not allowed for security reasons."
        )
        super().__init__(message)


class ExtensionNotAllowedError(ValueError):
    """Raised when attachment extension is not in the allow-list."""

    def __init__(self, filename: str, extension: str | None) -> None:
        self.filename = filename
        self.extension = extension
        if extension is None:
            message = (
                f"Attachment '{filename}' has no file extension. "
                f"Files without extensions are not allowed."
            )
        else:
            message = (
                f"Attachment '{filename}' has extension '.{extension}' which is not "
                f"in the allowed extensions list."
            )
        super().__init__(message)


class AttachmentSizeError(ValueError):
    """Raised when attachment content exceeds the maximum allowed size."""

    def __init__(self, filename: str, actual_size: int, max_size: int | None = None) -> None:
        self.filename = filename
        self.actual_size = actual_size
        self.max_size = max_size if max_size is not None else DEFAULT_MAX_ATTACHMENT_SIZE
        message = (
            f"Attachment '{filename}' exceeds maximum size of "
            f"{self.max_size / (1024 * 1024):.2f}MB "
            f"(size: {actual_size / (1024 * 1024):.2f}MB)"
        )
        super().__init__(message)
