<!DOCTYPE html>
<html lang="en">
<head>
    % include("head")
</head>
<body>
    % include("navbar")
    <h1>
    % if defined("topdir") and topdir:
        {{ path }}
    % else:
        % parts = path.split("/")
        % for p in xrange(len(parts)-1):
            % parent = "/".join(parts[1:p+1])
            <a href="{{ app.get_url('browse', path=parent) if parent else app.get_url('base') }}">{{ parts[p] }}</a>
            <span> / </span>
        % end
        {{ parts[-1] }}
    % end
    </h1>
    % if not has_files:
    <p>No files in directory</p>
    % else:
    <table class="browser">
        <thead>
            <tr>
                <th colspan="3">Name</th>
                <th>Mimetype</th>
                <th>Modified</th>
                <th>Size</th>
            </tr>
        </thead>
        <tbody>
    % end
