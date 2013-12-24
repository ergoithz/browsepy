<!DOCTYPE html>
<html lang="en">
<head>
    % include("head")
</head>
<body>
    % include("navbar")
    <h1>{{ app.config["browsepy.title"] }}</h1>
    <ul class="main-menu">
        % for name, url in extra_links:
            <li><a href="{{ url }}">{{ name }}</a></li>
        % end
    </ul>
    % include("footer")
</body>
</html>
