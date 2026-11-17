"""Operations package initializer and default registration."""

from shellsense.operations.archive_ops import CreateArchiveOperation
from shellsense.operations.cleanup_ops import CleanTempOperation
from shellsense.operations.duplicates import FindDuplicatesOperation
from shellsense.operations.file_ops import FileListOperation, TrashFilesOperation
from shellsense.operations.process_ops import ListProcessesOperation, TerminateProcessOperation
from shellsense.operations.registry import GLOBAL_REGISTRY, BaseOperation, OperationRegistry
from shellsense.operations.system_info import SystemInfoOperation

# Register default operations
GLOBAL_REGISTRY.register(SystemInfoOperation())
GLOBAL_REGISTRY.register(FileListOperation())
GLOBAL_REGISTRY.register(TrashFilesOperation())
GLOBAL_REGISTRY.register(ListProcessesOperation())
GLOBAL_REGISTRY.register(TerminateProcessOperation())
GLOBAL_REGISTRY.register(CreateArchiveOperation())
GLOBAL_REGISTRY.register(CleanTempOperation())
GLOBAL_REGISTRY.register(FindDuplicatesOperation())

__all__ = [
    "GLOBAL_REGISTRY",
    "BaseOperation",
    "OperationRegistry",
    "SystemInfoOperation",
    "FileListOperation",
    "TrashFilesOperation",
    "ListProcessesOperation",
    "TerminateProcessOperation",
    "CreateArchiveOperation",
    "CleanTempOperation",
    "FindDuplicatesOperation",
]
