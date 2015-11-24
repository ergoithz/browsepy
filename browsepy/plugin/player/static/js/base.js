(function(){
    var $player = $('.jp-jplayer'),
        format = $player.attr('data-player-format'),
        media = {},
        options = {
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
        };
    if($player.is(['data-player-urls]'])){
        var list = [],
            urls = $player.attr('data-player-urls').split('|');
        for(var i=0, o; o=urls[i++];){

        }
    }
    else{
        media[format] = $player.attr('data-player-url');
    }
    $player.jPlayer(options);
}());
