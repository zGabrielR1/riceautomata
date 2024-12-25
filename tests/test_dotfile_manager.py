import os
import pytest
from src.dotfile import DotfileManager

def test_init(dotfile_manager):
    """Test DotfileManager initialization."""
    assert isinstance(dotfile_manager, DotfileManager)
    
def test_discover_dotfile_directories(dotfile_manager, sample_dotfiles):
    """Test dotfile directory discovery."""
    dirs = dotfile_manager._discover_dotfile_directories(sample_dotfiles, None, None, False)
    assert dirs
    assert any(".config" in d for d in dirs)
    
def test_apply_dotfiles(dotfile_manager, sample_dotfiles, temp_dir):
    """Test applying dotfiles."""
    target_dir = os.path.join(temp_dir, "home")
    os.makedirs(target_dir)
    
    result = dotfile_manager.apply_dotfiles(
        sample_dotfiles,
        target_dir=target_dir,
        stow_options=["-v"],
        package_manager=None
    )
    assert result
    assert os.path.exists(os.path.join(target_dir, ".bashrc"))
    
def test_process_templates(dotfile_manager, sample_templates, temp_dir):
    """Test template processing."""
    context = {
        "user_name": "test_user",
        "user_email": "test@example.com",
        "hostname": "test-host"
    }
    
    output_dir = os.path.join(temp_dir, "output")
    os.makedirs(output_dir)
    
    result = dotfile_manager._process_templates(
        sample_templates,
        output_dir,
        context
    )
    assert result
    
    # Check processed files
    with open(os.path.join(output_dir, "bashrc"), "r") as f:
        content = f.read()
        assert "test_user" in content
        assert "test@example.com" in content
        
def test_backup_restore(dotfile_manager, sample_dotfiles, temp_dir):
    """Test backup and restore functionality."""
    # Create backup
    backup_dir = os.path.join(temp_dir, "backups")
    os.makedirs(backup_dir)
    
    backup_name = dotfile_manager.create_backup(
        sample_dotfiles,
        backup_dir,
        "test_backup"
    )
    assert backup_name
    assert os.path.exists(os.path.join(backup_dir, backup_name))
    
    # Restore backup
    restore_dir = os.path.join(temp_dir, "restore")
    os.makedirs(restore_dir)
    
    result = dotfile_manager.restore_backup(
        backup_name,
        backup_dir,
        restore_dir
    )
    assert result
    assert os.path.exists(os.path.join(restore_dir, ".bashrc"))
    
def test_error_handling(dotfile_manager, temp_dir):
    """Test error handling for invalid operations."""
    # Test with non-existent directory
    invalid_dir = os.path.join(temp_dir, "nonexistent")
    result = dotfile_manager.apply_dotfiles(
        invalid_dir,
        target_dir=temp_dir
    )
    assert not result
    
def test_package_installation(dotfile_manager, mock_package_manager):
    """Test package installation functionality."""
    packages = ["test-pkg1", "test-pkg2"]
    result = dotfile_manager._install_missing_packages(
        packages,
        mock_package_manager
    )
    assert result
    assert "test-pkg1" in mock_package_manager.installed_packages
    assert "test-pkg2" in mock_package_manager.installed_packages
