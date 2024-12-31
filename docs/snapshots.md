# Snapshot System

The snapshot system in RiceAutomata allows you to create checkpoints of your current rice configuration and restore them at any time. This is particularly useful when you want to experiment with new themes, configurations, or dotfiles while having the ability to revert back to a known working state.

## Features

- Create snapshots of your current configuration
- Restore previous configurations
- List all available snapshots
- Delete unwanted snapshots
- Track installed packages and configuration changes
- Safe restoration with backup mechanism

## Commands

### Create a Snapshot

```bash
riceautomata snapshot create <name> [-d DESCRIPTION]
```

Creates a new snapshot of your current configuration. The snapshot includes:
- All dotfiles from ~/.config
- List of installed packages
- Timestamp and description (optional)

Example:
```bash
riceautomata snapshot create default -d "My stable configuration"
```

### Restore a Snapshot

```bash
riceautomata snapshot restore <name>
```

Restores your system to a previous snapshot. This will:
- Back up your current configuration
- Restore dotfiles from the snapshot
- Install missing packages that were present in the snapshot
- Remove packages that were not present in the snapshot

Example:
```bash
riceautomata snapshot restore default
```

### List Snapshots

```bash
riceautomata snapshot list
```

Lists all available snapshots with their details:
- Name
- Creation timestamp
- Description (if provided)
- Number of packages tracked

### Delete a Snapshot

```bash
riceautomata snapshot delete <name>
```

Deletes a snapshot and its associated files.

Example:
```bash
riceautomata snapshot delete old-config
```

## Best Practices

1. **Create Regular Snapshots**: Make a snapshot before making significant changes to your configuration.
2. **Use Descriptive Names**: Give your snapshots meaningful names that describe their purpose.
3. **Add Descriptions**: Use the `-d` flag to add descriptions to your snapshots for better organization.
4. **Clean Up Old Snapshots**: Remove snapshots you no longer need to save disk space.
5. **Test Restoration**: Periodically test restoring snapshots to ensure they work as expected.

## Safety Features

- Automatic backup of current configuration before restoration
- Confirmation prompts for destructive operations
- Error handling and logging
- Rollback mechanism if restoration fails
