(function() {
  if (document.querySelectorAll) {
    var
      forms = document.querySelectorAll('html.autosubmit-support form.autosubmit'),
      i = forms.length;
    while (i--) {
      files = forms[i].querySelectorAll('input[type=file]');
      files[0].addEventListener('change', (function(form) {
        return function(e) {
          form.submit();
        };
      }(forms[i])));
    }
  }
}());
