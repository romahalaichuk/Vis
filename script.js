document
	.getElementById("download-button")
	.addEventListener("click", function () {
		var a = document.createElement("a");
		a.href = "https://romahalaichuk.github.io/Vis/index.html";
		a.download = "index.html";
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
	});
