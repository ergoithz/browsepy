//Source: https://stackoverflow.com/questions/47851329/jquery-image-gallery-from-json-file

var $list = $('<ul>', {
    class: 'image-list'
});
var $overlay = $('#overlay');
var $image = $("#fullSize");

var $imageObjects = null

function show_single_file(src, caption) {
    $image.attr("src", src);
    $image.data("new", true);
    $("#caption").text(caption);
    $("#full-image-link").attr("href", src);
    $overlay.show();

}
function closeOverlay() {
    $image.attr('src', '');
    $overlay.hide();
}
function plusSlides(offset) {
    let index = ($image.data("index") + offset + $imageObjects.length) % $imageObjects.length;
    showImage(index);
}

function showImage(index) {
    let src = $imageObjects[index].url
    $image.attr("src", src);
    $image.data("index", index);
    $("#caption").text($imageObjects[index].caption);
    $("#full-image-link").attr("href", src);
    $("#numbertext").text(index + "/" + $imageObjects.length)
    $overlay.show();
}

function draw_gallery(jsonpath, current_image) {
    $.getJSON(jsonpath,
        function (data) {
            //prepare variables to be used later 
            $imageObjects = data;

            $(data).each(function (i, photoObject) {
                if ($image.data("new")) {
                    if ($image.attr("src") == photoObject.url) {
                        $image.data("new", false);
                        $image.data("index", i);
                    }
                }
                $list.append(`<li class="imageGallery">
            <a href="${photoObject.url}">
                <img class="thumbnail demo" data-index="${i}" 
                      src="${photoObject.thumbnail}" 
                      alt="${photoObject.caption}"/>
                <div class="thumbnail-caption">${photoObject.caption}</div>
            </a>
        </li>`);
            });

            $('#image-list').prepend($list)
            $('.imageGallery').on('click', 'img', function (e) {
                e.preventDefault();
                $index = $(this).data('index');
                showImage($index)
            });

            $(document).keydown(function (e) {
                if ($image.attr("src")) {
                    if (e.which == 27) {
                        closeOverlay();
                    }
                    if (e.which == 39) {
                        plusSlides(+1);
                    }
                    if (e.which == 37) {
                        plusSlides(-1);
                    }
                }
            });

        });
}