(function(){
    var $player = $('.jp-jplayer'),
        format = $player.attr('data-player-format'),
        media = {};
    media[format] = $player.attr('data-player-url');
    $player.jPlayer({
        ready: function (event) {
            $(this).jPlayer("setMedia", media).jPlayer("play");
        },
        swfPath: $player.attr('data-player-swf'),
        supplied: format,
        wmode: "window",
        useStateClassSkin: true,
        autoBlur: false,
        smoothPlayBar: true,
        keyEnabled: true,
        remainingDuration: true,
        toggleDuration: true,
        cssSelectorAncestor: '.jp-audio'
    });
}());
