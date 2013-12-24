<tr>
    <td class="{{ 'dir' if f.is_directory else 'file' }}-icon"></td>
    <td>\\
        <a href="{{ app.get_url('browse', path=f.relpath) if f.relpath else app.get_url('base') }}">{{ f.basename }}</a>\\
    </td>
    <td>
        % if f.can_remove:
        <a href="{{ app.get_url('remove_confirm', path=f.relpath) }}" class="remove button"></a>
        % end
        % if f.can_download:
        <a href="{{ app.get_url('download_directory' if f.is_directory else 'download_file', path=f.relpath) }}" class="download button"></a>
        % end
    </td>
    <td>{{ f.type }}</td>
    <td>{{ f.modified }}</td>
    <td>{{ "" if f.is_directory else f.size }}</td>
</tr>
