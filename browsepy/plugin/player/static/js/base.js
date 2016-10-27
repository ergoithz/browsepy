(function() {
  var
    $player = $('.jp-jplayer'),
    options = {
      swfPath: $player.attr('data-player-swf'),
      wmode: "window",
      useStateClassSkin: true,
      autoBlur: false,
      smoothPlayBar: true,
      keyEnabled: true,
      remainingDuration: true,
      toggleDuration: true,
      cssSelectorAncestor: '.jp-audio',
      playlistOptions: {
        autoPlay: true
      }
    };
  if ($player.is('[data-player-urls]')) {
    var
      list = [],
      formats = [],
      urls = $player.attr('data-player-urls').split('|'),
      sel = {
        jPlayer: $player,
        cssSelectorAncestor: '.jp-audio'
      };
    for (var i = 0, stack = [], d; o = urls[i++];) {
      stack.push(o);
      if (stack.length == 3) {
        d = {
          title: stack[1]
        };
        d[stack[0]] = stack[2];
        list.push(d);
        formats.push(stack[0]);
        stack.splice(0, stack.length);
      }
    }
    options.supplied = formats.join(', ');
    new jPlayerPlaylist(sel, list, options);
  } else {
    var
      media = {},
      format = $player.attr('data-player-format');
    media.title = $player.attr('data-player-title');
    media[format] = $player.attr('data-player-url');
    options.supplied = format;
    options.ready = function(event) {
      $(this).jPlayer("setMedia", media).jPlayer("play");
    };
    $player.jPlayer(options);
  }
}());
