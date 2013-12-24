<!DOCTYPE html>
<html lang="en">
<head>
    % include("head")
</head>
<body>
    % include("navbar")
    <h1>Remove</h1>
    <form method="post">
        <p>Are you sure you wanna remove <strong>{{ path }}</strong> ?</p>
        <input type="hidden" name="backurl" value="{{ backurl }}"/>
        <input type="submit" value="Yes" /> <a href="{{ backurl }}" alt="Go back">Cancel</a>
    </form>
    % include("footer")
</body>
</html>
