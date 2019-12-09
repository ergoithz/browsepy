"""Playable file classes."""

from werkzeug.utils import cached_property

from browsepy.file import Node, File, Directory


from .playlist import iter_pls_entries, iter_m3u_entries


class PlayableNode(Node):
    """Base class for playable nodes."""

    playable_list = False

    @cached_property
    def is_playable(self):
        """
        Get if node is playable.

        :returns: True if node is playable, False otherwise
        :rtype: bool
        """
        return self.detect(self)

    @classmethod
    def detect(cls, node):
        """Check if class supports node."""
        kls = cls.directory_class if node.is_directory else cls.file_class
        return kls.detect(node)


@PlayableNode.register_file_class
class PlayableFile(PlayableNode, File):
    """Generic node for filenames with extension."""

    title = None
    duration = None
    playable_extensions = {
        'mp3': 'audio/mpeg',
        'ogg': 'audio/ogg',
        'oga': 'audio/ogg',
        'm4a': 'audio/mp4',
        'wav': 'audio/wav',
        'm3u': 'audio/x-mpegurl',
        'm3u8': 'audio/x-mpegurl',
        'pls': 'audio/x-scpls',
         }
    playable_list_parsers = {
        'pls': iter_pls_entries,
        'm3u': iter_m3u_entries,
        'm3u8': iter_m3u_entries,
        }

    @cached_property
    def playable_list(self):
        """Get whether file is a playlist."""
        return self.extension in self.playable_list_parsers

    @cached_property
    def mimetype(self):
        """Get mimetype."""
        return self.detect_mimetype(self.path)

    @cached_property
    def extension(self):
        """Get filename extension."""
        return self.detect_extension(self.path)

    def entries(self):
        """Iterate playlist files."""
        parser = self.playable_list_parsers.get(self.extension)
        if parser:
            for options in parser(self):
                node = self.file_class(**options, app=self.app)
                if not node.is_excluded:
                    yield node

    @classmethod
    def detect(cls, node):
        """Get whether file is playable."""
        return (
            not node.is_directory and
            cls.detect_extension(node.path) in cls.playable_extensions
            )

    @classmethod
    def detect_extension(cls, path):
        """Detect extension from given path."""
        for extension in cls.playable_extensions:
            if path.endswith('.%s' % extension):
                return extension
        return None

    @classmethod
    def detect_mimetype(cls, path):
        """Detect mimetype by its extension."""
        return cls.playable_extensions.get(
            cls.detect_extension(path),
            'application/octet-stream'
            )


@PlayableNode.register_directory_class
class PlayableDirectory(PlayableNode, Directory):
    """Playable directory node."""

    playable_list = True

    def entries(self, sortkey=None, reverse=None):
        """Iterate playable directory playable files."""
        for node in self.listdir(sortkey=sortkey, reverse=reverse):
            if not node.is_directory and node.is_playable:
                yield node

    @classmethod
    def detect(cls, node):
        """Detect if given node contains playable files."""
        return node.is_directory and any(
            child.is_playable
            for child in node._listdir()
            if not child.is_directory
            )
