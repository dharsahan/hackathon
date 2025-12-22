"""
Desktop Notifications
=====================

Provides desktop notification support for file organization events.
Uses libnotify on Linux for native notifications.
"""

import subprocess
from pathlib import Path
from typing import Optional
from enum import Enum
from dataclasses import dataclass

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class NotificationType(Enum):
    """Types of notifications."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class NotificationConfig:
    """Notification configuration."""
    enabled: bool = True
    show_on_organize: bool = True
    show_on_duplicate: bool = True
    show_on_sensitive: bool = True
    show_on_error: bool = True
    timeout_ms: int = 5000  # 5 seconds


class DesktopNotifier:
    """Sends desktop notifications for file organization events.
    
    Uses notify-send on Linux for native notifications.
    """
    
    APP_NAME = "Smart File Organizer"
    ICON_PATH = "folder"  # Uses system icon
    
    def __init__(self, config: Optional[NotificationConfig] = None):
        """Initialize the notifier.
        
        Args:
            config: Notification configuration.
        """
        self.config = config or NotificationConfig()
        self._available = self._check_availability()
        
        if self._available:
            logger.debug("Desktop notifications available")
        else:
            logger.warning("Desktop notifications not available (notify-send not found)")
    
    def _check_availability(self) -> bool:
        """Check if notification system is available."""
        try:
            result = subprocess.run(
                ["which", "notify-send"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    @property
    def is_available(self) -> bool:
        """Check if notifications are available and enabled."""
        return self._available and self.config.enabled
    
    def _get_icon(self, notif_type: NotificationType) -> str:
        """Get icon for notification type."""
        icons = {
            NotificationType.INFO: "dialog-information",
            NotificationType.SUCCESS: "emblem-ok-symbolic",
            NotificationType.WARNING: "dialog-warning",
            NotificationType.ERROR: "dialog-error",
        }
        return icons.get(notif_type, "folder")
    
    def _get_urgency(self, notif_type: NotificationType) -> str:
        """Get urgency level for notification type."""
        urgencies = {
            NotificationType.INFO: "low",
            NotificationType.SUCCESS: "normal",
            NotificationType.WARNING: "normal",
            NotificationType.ERROR: "critical",
        }
        return urgencies.get(notif_type, "normal")
    
    def send(
        self,
        title: str,
        message: str,
        notif_type: NotificationType = NotificationType.INFO
    ) -> bool:
        """Send a desktop notification.
        
        Args:
            title: Notification title.
            message: Notification body.
            notif_type: Type of notification.
        
        Returns:
            True if notification was sent successfully.
        """
        if not self.is_available:
            return False
        
        try:
            cmd = [
                "notify-send",
                "--app-name", self.APP_NAME,
                "--icon", self._get_icon(notif_type),
                "--urgency", self._get_urgency(notif_type),
                "--expire-time", str(self.config.timeout_ms),
                title,
                message
            ]
            
            subprocess.run(cmd, capture_output=True, timeout=5)
            logger.debug(f"Notification sent: {title}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return False
    
    def notify_organized(self, filename: str, category: str, destination: str) -> None:
        """Notify that a file was organized.
        
        Args:
            filename: Name of the organized file.
            category: Category the file was organized into.
            destination: Destination path.
        """
        if not self.config.show_on_organize:
            return
        
        dest_short = str(Path(destination).parent.name)
        self.send(
            f"📁 File Organized",
            f"{filename}\n→ {category}/{dest_short}",
            NotificationType.SUCCESS
        )
    
    def notify_duplicate(self, filename: str, action: str) -> None:
        """Notify that a duplicate was found.
        
        Args:
            filename: Name of the duplicate file.
            action: Action taken (quarantine, skip, delete).
        """
        if not self.config.show_on_duplicate:
            return
        
        self.send(
            f"🔄 Duplicate Found",
            f"{filename}\nAction: {action}",
            NotificationType.WARNING
        )
    
    def notify_sensitive(self, filename: str) -> None:
        """Notify that a sensitive file was detected.
        
        Args:
            filename: Name of the sensitive file.
        """
        if not self.config.show_on_sensitive:
            return
        
        self.send(
            f"🔒 Sensitive File Detected",
            f"{filename}\nMoved to secure vault",
            NotificationType.WARNING
        )
    
    def notify_error(self, filename: str, error: str) -> None:
        """Notify of a processing error.
        
        Args:
            filename: Name of the file that failed.
            error: Error message.
        """
        if not self.config.show_on_error:
            return
        
        self.send(
            f"❌ Processing Error",
            f"{filename}\n{error[:100]}",
            NotificationType.ERROR
        )
    
    def notify_started(self) -> None:
        """Notify that the organizer has started."""
        self.send(
            f"🚀 {self.APP_NAME}",
            "Started watching for files",
            NotificationType.INFO
        )
    
    def notify_stopped(self, stats: dict) -> None:
        """Notify that the organizer has stopped.
        
        Args:
            stats: Processing statistics.
        """
        self.send(
            f"⏹️ {self.APP_NAME}",
            f"Stopped\nProcessed: {stats.get('processed', 0)} files",
            NotificationType.INFO
        )
