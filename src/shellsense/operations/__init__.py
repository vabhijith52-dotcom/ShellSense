"""Operations package initializer and default registration."""

from shellsense.operations.archive_ops import CreateArchiveOperation, ExtractArchiveOperation
from shellsense.operations.cleanup_ops import CleanTempOperation
from shellsense.operations.duplicates import FindDuplicatesOperation
from shellsense.operations.file_ops import (
    AppendTextOperation,
    BatchRenameOperation,
    CopyOperation,
    CreateFileOperation,
    CreateFolderOperation,
    DeleteEmptyFoldersOperation,
    FileListOperation,
    MoveOperation,
    OrganizeByTypeOperation,
    RenameOperation,
    TrashFilesOperation,
    TrashFolderOperation,
)
from shellsense.operations.meta_ops import (
    CancelTaskOperation,
    ExplainLastOperation,
    HelpOperation,
    ShowHistoryOperation,
    ShowPermissionsOperation,
    ShowTasksOperation,
    UndoOperation,
)
from shellsense.operations.process_ops import ListProcessesOperation, TerminateProcessOperation
from shellsense.operations.registry import GLOBAL_REGISTRY, BaseOperation, OperationRegistry
from shellsense.operations.retrieval_ops import FileRetrievalOperation
from shellsense.operations.system_info import SystemInfoOperation

# Register default operations
GLOBAL_REGISTRY.register(SystemInfoOperation())
GLOBAL_REGISTRY.register(FileListOperation())
GLOBAL_REGISTRY.register(TrashFilesOperation())
GLOBAL_REGISTRY.register(TrashFolderOperation())
GLOBAL_REGISTRY.register(DeleteEmptyFoldersOperation())
GLOBAL_REGISTRY.register(CreateFolderOperation())
GLOBAL_REGISTRY.register(CreateFileOperation())
GLOBAL_REGISTRY.register(AppendTextOperation())
GLOBAL_REGISTRY.register(MoveOperation())
GLOBAL_REGISTRY.register(CopyOperation())
GLOBAL_REGISTRY.register(RenameOperation())
GLOBAL_REGISTRY.register(BatchRenameOperation())
GLOBAL_REGISTRY.register(OrganizeByTypeOperation())
GLOBAL_REGISTRY.register(FileRetrievalOperation())
GLOBAL_REGISTRY.register(ListProcessesOperation())
GLOBAL_REGISTRY.register(TerminateProcessOperation())
GLOBAL_REGISTRY.register(CreateArchiveOperation())
GLOBAL_REGISTRY.register(ExtractArchiveOperation())
GLOBAL_REGISTRY.register(CleanTempOperation())
GLOBAL_REGISTRY.register(FindDuplicatesOperation())
GLOBAL_REGISTRY.register(HelpOperation())
GLOBAL_REGISTRY.register(ShowPermissionsOperation())
GLOBAL_REGISTRY.register(ShowHistoryOperation())
GLOBAL_REGISTRY.register(ShowTasksOperation())
GLOBAL_REGISTRY.register(CancelTaskOperation())
GLOBAL_REGISTRY.register(ExplainLastOperation())
GLOBAL_REGISTRY.register(UndoOperation())

__all__ = [
    "GLOBAL_REGISTRY",
    "BaseOperation",
    "OperationRegistry",
    "SystemInfoOperation",
    "FileListOperation",
    "TrashFilesOperation",
    "TrashFolderOperation",
    "DeleteEmptyFoldersOperation",
    "CreateFolderOperation",
    "CreateFileOperation",
    "AppendTextOperation",
    "MoveOperation",
    "CopyOperation",
    "RenameOperation",
    "BatchRenameOperation",
    "OrganizeByTypeOperation",
    "FileRetrievalOperation",
    "ListProcessesOperation",
    "TerminateProcessOperation",
    "CreateArchiveOperation",
    "ExtractArchiveOperation",
    "CleanTempOperation",
    "FindDuplicatesOperation",
    "HelpOperation",
    "ShowPermissionsOperation",
    "ShowHistoryOperation",
    "ShowTasksOperation",
    "CancelTaskOperation",
    "ExplainLastOperation",
    "UndoOperation",
]
