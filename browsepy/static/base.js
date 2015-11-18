(function(){
    if(document.querySelectorAll && document.addEventListener){
        var forms = document.querySelectorAll('form'),
            i, j, form, button, inputs, files, buttons;
        for(i = 0; form = forms[i++];){
            buttons = form.querySelectorAll('input[type=submit], input[type=reset]');
            inputs = form.querySelectorAll('input');
            files = form.querySelectorAll('input[type=file]');
            if(files.length == 1 && inputs.length - buttons.length == 1){
                files[0].addEventListener('change', (function(form){
                    return function(e){
                        form.submit();
                    };
                }(form)));
                for(j = 0; button = buttons[j++];){
                    button.style.display = 'none';
                }
            }
        }
    }
}());
