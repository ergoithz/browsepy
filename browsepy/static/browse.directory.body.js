(function() {
  if (document.querySelectorAll) {
    var
      forms = document.querySelectorAll('html.autosubmit-support form.autosubmit'),
      i = forms.length;
    while (i--) {
      var
        input = forms[i].querySelectorAll('input[type=file]')[0],
        label = forms[i].querySelectorAll('label')[0];
      input.addEventListener('change', (function(form) {
        return function() {
          form.submit();
        };
      }(forms[i])));
      label.tabIndex = 0;
    }
  }
}());
