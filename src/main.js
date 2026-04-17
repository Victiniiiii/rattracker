let invoke, Command;
const tauri = window.__TAURI__;
invoke = tauri.core.invoke;
Command = tauri.shell.Command;

let fileServerPort = null;

async function initFileServer() {
	fileServerPort = await invoke("get_server_port");
}

function fileUrl(path) {
	return `http://127.0.0.1:${fileServerPort}/file?path=${encodeURIComponent(path)}`;
}

async function fetchText(path) {
	const res = await fetch(fileUrl(path));
	if (!res.ok) throw new Error(`Failed to fetch ${path}`);
	return res.text();
}

const STORAGE_KEY = "rattracker_config";

const DEFAULTS = {
	mog2_history: 120,
	mog2_threshold: 40,
	mog2_detect_shadow: false,
	morph_open_k: 3,
	morph_close_k: 15,
	min_contour_area: 300,
	max_contour_area: 12000,
	trail_len: 40,
	debug_frames: 0,
	pool_west: "",
	pool_north: "",
	pool_east: "",
	pool_south: "",
	platform_nw: "",
	platform_ne: "",
	platform_se: "",
	platform_sw: "",
	quadrantcross: false,
	platformcross: false,
	paraplatform_enabled: false,
	paraplatform_scale: 4,
	proximity: false,
	latency: false,
	tracemapcolor_enabled: false,
	tracemapcolor: "#00ffff",
	language: "en",
};

const I18N = {
	en: {
		title: "Rat Tracker",
		settings: "Settings",
		detection: "Detection",
		mog2_history: "MOG2 History",
		mog2_history_desc: "Number of frames used to build the background model. Higher = slower adaptation, better for stable cameras.",
		mog2_threshold: "MOG2 Threshold",
		mog2_threshold_desc: "Sensitivity of foreground detection. Lower = more sensitive (more false positives). Higher = less sensitive (may miss rat).",
		detect_shadows: "Detect Shadows",
		detect_shadows_desc: "Enables shadow detection in the background subtractor. Slightly slower but reduces shadow artifacts being mistaken for the rat.",
		morph_open: "Morph Open Kernel",
		morph_open_desc: "Size of the erosion/dilation kernel used to remove small noise blobs. Must be odd. Larger values remove bigger noise at the cost of detail.",
		morph_close: "Morph Close Kernel",
		morph_close_desc: "Size of the kernel used to fill gaps and holes in the detected rat blob. Must be odd. Larger values bridge bigger gaps.",
		min_area: "Min Contour Area (px²)",
		min_area_desc: "Minimum blob size to be considered the rat. Increase if small noise is being detected as the rat.",
		max_area: "Max Contour Area (px²)",
		max_area_desc: "Maximum blob size to be considered the rat. Decrease if large reflections or objects are being falsely detected.",
		trail_len: "Trail Length (frames)",
		trail_len_desc: "How many past positions are drawn as a movement trail in the output video. Purely visual.",
		debug_frames: "Debug Frames",
		debug_frames_desc: "Saves the first N foreground mask images to disk for troubleshooting detection. Set to 0 to disable.",
		pool_calib: "Pool Calibration Cache",
		pool_note: "Auto-filled after first calibration. Edit to reuse across videos of the same setup without re-clicking.",
		pool_west: "Pool West (x,y)",
		pool_north: "Pool North (x,y)",
		pool_east: "Pool East (x,y)",
		pool_south: "Pool South (x,y)",
		platform_calib: "Platform Calibration Cache",
		platform_note: "Required for platform-dependent features. Auto-filled after first platform calibration.",
		platform_nw: "Platform NW (x,y)",
		platform_ne: "Platform NE (x,y)",
		platform_se: "Platform SE (x,y)",
		platform_sw: "Platform SW (x,y)",
		features: "Analysis Features",
		features_note: "Enable optional analyses. Platform-dependent features require platform calibration coordinates.",
		quadrantcross: "Quadrant Crossings",
		quadrantcross_desc: "Counts how many times the rat exits each quadrant (NE/NW/SE/SW). Adds exit counts to the summary and output video leaderboard.",
		platformcross: "Platform Crossings",
		platformcross_desc: "Counts how many times the rat exits the platform area. Requires platform calibration.",
		paraplatform: "ParaPlatform Analysis",
		paraplatform_desc: "Tracks time and distance spent in a scaled-up zone around the platform (e.g. 4× area = 2× side length). Requires platform calibration.",
		paraplatform_scale: "Area Scale Factor",
		paraplatform_scale_desc: "The area multiplier for the ParaPlatform zone. A value of 4 means the zone has 4× the area of the real platform (2× side length).",
		proximity: "Proximity to Platform",
		proximity_desc: "Calculates the average distance from the rat to the platform center across all detected frames. Requires platform calibration.",
		latency: "Latency to Platform",
		latency_desc: "Records the time and distance travelled until the rat first steps onto the platform. Requires platform calibration.",
		tracemapcolor: "Tracemap Color",
		tracemapcolor_desc: "Color of the path line drawn on the tracemap image output.",
		save: "Save",
		cancel: "Cancel",
		select_video: "Select Video",
		no_file: "No video selected",
		start_time: "Start (s)",
		end_time: "End (s)",
		pool_radius: "Radius (cm)",
		run: "Run",
		tab_video: "Video",
		tab_csv: "CSV",
		tab_summary: "Summary",
		tab_tracemap: "Tracemap",
		tab_heatmap: "Heatmap",
	},
	fr: {
		title: "Rat Tracker",
		settings: "Paramètres",
		detection: "Détection",
		mog2_history: "Historique MOG2",
		mog2_history_desc: "Nombre d'images utilisées pour construire le modèle de fond. Plus élevé = adaptation plus lente, meilleur pour les caméras stables.",
		mog2_threshold: "Seuil MOG2",
		mog2_threshold_desc: "Sensibilité de la détection du premier plan. Plus bas = plus sensible (faux positifs). Plus haut = moins sensible (peut rater le rat).",
		detect_shadows: "Détecter les ombres",
		detect_shadows_desc: "Active la détection d'ombres. Légèrement plus lent mais réduit les artefacts d'ombres confondus avec le rat.",
		morph_open: "Noyau ouverture morph.",
		morph_open_desc: "Taille du noyau pour supprimer le bruit. Doit être impair. Des valeurs plus grandes suppriment un bruit plus important.",
		morph_close: "Noyau fermeture morph.",
		morph_close_desc: "Taille du noyau pour combler les trous dans le blob détecté. Doit être impair.",
		min_area: "Surface contour min. (px²)",
		min_area_desc: "Taille minimale du blob pour être considéré comme le rat. Augmentez si du bruit est détecté.",
		max_area: "Surface contour max. (px²)",
		max_area_desc: "Taille maximale du blob pour être considéré comme le rat. Diminuez si des reflets sont détectés.",
		trail_len: "Longueur trace (images)",
		trail_len_desc: "Nombre de positions passées dessinées comme trace dans la vidéo de sortie. Purement visuel.",
		debug_frames: "Images de débogage",
		debug_frames_desc: "Sauvegarde les N premiers masques de premier plan pour le débogage. 0 pour désactiver.",
		pool_calib: "Cache calibration bassin",
		pool_note: "Rempli automatiquement après la première calibration. Modifiez pour réutiliser sur plusieurs vidéos.",
		pool_west: "Bassin Ouest (x,y)",
		pool_north: "Bassin Nord (x,y)",
		pool_east: "Bassin Est (x,y)",
		pool_south: "Bassin Sud (x,y)",
		platform_calib: "Cache calibration plateforme",
		platform_note: "Requis pour les fonctions dépendantes de la plateforme. Rempli automatiquement après calibration.",
		platform_nw: "Plateforme NO (x,y)",
		platform_ne: "Plateforme NE (x,y)",
		platform_se: "Plateforme SE (x,y)",
		platform_sw: "Plateforme SO (x,y)",
		features: "Fonctions d'analyse",
		features_note: "Les fonctions dépendantes de la plateforme nécessitent des coordonnées de calibration.",
		quadrantcross: "Croisements de quadrants",
		quadrantcross_desc: "Compte le nombre de fois que le rat quitte chaque quadrant.",
		platformcross: "Croisements de plateforme",
		platformcross_desc: "Compte le nombre de fois que le rat quitte la plateforme. Nécessite la calibration.",
		paraplatform: "Analyse ParaPlateforme",
		paraplatform_desc: "Suit le temps et la distance dans une zone agrandie autour de la plateforme.",
		paraplatform_scale: "Facteur d'échelle de surface",
		paraplatform_scale_desc: "Multiplicateur de surface pour la zone ParaPlateforme. 4 = 4× la surface réelle.",
		proximity: "Proximité de la plateforme",
		proximity_desc: "Calcule la distance moyenne du rat au centre de la plateforme.",
		latency: "Latence vers la plateforme",
		latency_desc: "Enregistre le temps et la distance jusqu'à la première montée sur la plateforme.",
		tracemapcolor: "Couleur tracemap",
		tracemapcolor_desc: "Couleur du tracé sur l'image tracemap.",
		save: "Enregistrer",
		cancel: "Annuler",
		select_video: "Choisir une vidéo",
		no_file: "Aucun video sélectionné",
		start_time: "Début (s)",
		end_time: "Fin (s)",
		pool_radius: "Rayon (cm)",
		run: "Lancer",
		tab_video: "Vidéo",
		tab_csv: "CSV",
		tab_summary: "Résumé",
		tab_tracemap: "Carte de Trajectoire",
		tab_heatmap: "Carte de Chaleur",
	},
	tr: {
		title: "Fare İzleyici",
		settings: "Ayarlar",
		detection: "Algılama",
		mog2_history: "MOG2 Geçmişi",
		mog2_history_desc: "Arka plan modelini oluşturmak için kullanılan kare sayısı. Yüksek = yavaş uyum, sabit kameralar için daha iyi.",
		mog2_threshold: "MOG2 Eşiği",
		mog2_threshold_desc: "Ön plan algılama hassasiyeti. Düşük = daha hassas (yanlış pozitifler). Yüksek = daha az hassas.",
		detect_shadows: "Gölgeleri Algıla",
		detect_shadows_desc: "Gölge tespitini etkinleştirir. Biraz daha yavaş ama gölge artefaktlarını azaltır.",
		morph_open: "Morfoloji Açma Çekirdeği",
		morph_open_desc: "Küçük gürültü bloblarını kaldırmak için kullanılan çekirdek boyutu. Tek sayı olmalı.",
		morph_close: "Morfoloji Kapama Çekirdeği",
		morph_close_desc: "Algılanan rat blobundaki boşlukları doldurmak için çekirdek boyutu. Tek sayı olmalı.",
		min_area: "Min Kontur Alanı (px²)",
		min_area_desc: "Rat olarak kabul edilmek için minimum blob boyutu. Gürültü algılanıyorsa artırın.",
		max_area: "Maks Kontur Alanı (px²)",
		max_area_desc: "Rat olarak kabul edilmek için maksimum blob boyutu. Yansımalar algılanıyorsa azaltın.",
		trail_len: "İz Uzunluğu (kare)",
		trail_len_desc: "Çıktı videosunda hareket izi olarak çizilen geçmiş konum sayısı. Yalnızca görsel.",
		debug_frames: "Hata Ayıklama Kareleri",
		debug_frames_desc: "İlk N ön plan maskesini diske kaydeder. 0 = devre dışı.",
		pool_calib: "Havuz Kalibrasyon Önbelleği",
		pool_note: "İlk kalibrasyondan sonra otomatik doldurulur. Aynı kurulum için farklı videolarda yeniden kullanmak için düzenleyin.",
		pool_west: "Havuzun Batısı (x,y)",
		pool_north: "Havuzun Kuzeyi (x,y)",
		pool_east: "Havuzun Doğusu (x,y)",
		pool_south: "Havuzun Güneyi (x,y)",
		platform_calib: "Platform Kalibrasyon Önbelleği",
		platform_note: "Platforma bağlı özellikler için gerekli. İlk kalibrasyondan sonra otomatik doldurulur.",
		platform_nw: "Platform KB (x,y)",
		platform_ne: "Platform KD (x,y)",
		platform_se: "Platform GD (x,y)",
		platform_sw: "Platform GB (x,y)",
		features: "Analiz Özellikleri",
		features_note: "İsteğe bağlı analizleri etkinleştirin. Platforma bağlı özellikler kalibrasyon gerektirir.",
		quadrantcross: "Çeyrek Geçişleri",
		quadrantcross_desc: "Ratın her çeyrekten kaç kez çıktığını sayar.",
		platformcross: "Platform Geçişleri",
		platformcross_desc: "Ratın platformdan kaç kez çıktığını sayar. Platform kalibrasyonu gerektirir.",
		paraplatform: "ParaPlatform Analizi",
		paraplatform_desc: "Platform etrafında ölçeklendirilmiş bir bölgede geçirilen süre ve mesafeyi takip eder.",
		paraplatform_scale: "Alan Ölçek Faktörü",
		paraplatform_scale_desc: "ParaPlatform bölgesi için alan çarpanı. 4 = gerçek platformun 4× alanı.",
		proximity: "Platform Yakınlığı",
		proximity_desc: "Ratın platform merkezine olan ortalama mesafesini hesaplar.",
		latency: "Platform Gecikmesi",
		latency_desc: "Ratın platforma ilk adım atana kadar geçen süre ve mesafeyi kaydeder.",
		tracemapcolor: "Tracemap Rengi",
		tracemapcolor_desc: "Tracemap çıktı görüntüsündeki yol çizgisinin rengi.",
		save: "Kaydet",
		cancel: "İptal",
		select_video: "Video Seç",
		no_file: "Video seçilmedi",
		start_time: "Başlangıç (s)",
		end_time: "Bitiş (s)",
		pool_radius: "Yarıçap (cm)",
		run: "Çalıştır",
		tab_video: "Video",
		tab_csv: "CSV",
		tab_summary: "Özet",
		tab_tracemap: "İz Haritası",
		tab_heatmap: "Isı Haritası",
	},
};

const LANG_META = {
	en: { flag: "assets/uk.svg", name: "English" },
	fr: { flag: "assets/fr.svg", name: "Français" },
	tr: { flag: "assets/tr.svg", name: "Türkçe" },
};

let selectedFile = null;
let pythonProcess = null;
let cfg = { ...DEFAULTS };

function loadConfig() {
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		if (raw) return { ...DEFAULTS, ...JSON.parse(raw) };
	} catch (error) {
		console.warn("Error reading localStorage:", error);
	}
	return { ...DEFAULTS };
}

function saveConfig(newCfg) {
	try {
		localStorage.setItem(STORAGE_KEY, JSON.stringify(newCfg));
	} catch (error) {
		console.warn("Error saving to localStorage:", error);
	}
}

function translate(key) {
	return I18N[cfg.language]?.[key] ?? I18N.en[key] ?? key;
}

function applyI18n() {
	document.querySelectorAll("[data-i18n]").forEach(element => {
		const key = element.getAttribute("data-i18n");
		const input = element.querySelector("input");
		if (input) {
			element.childNodes[0].textContent = translate(key);
		} else {
			element.textContent = translate(key);
		}
	});

	document.querySelectorAll("[data-i18n-desc]").forEach(element => {
		element.textContent = translate(element.getAttribute("data-i18n-desc"));
	});

	if (!selectedFile) {
		document.getElementById("filePath").textContent = translate("no_file");
	}

	const meta = LANG_META[cfg.language];
	document.getElementById("langFlagSelected").src = meta.flag;
	document.getElementById("langNameSelected").textContent = meta.name;
}

function toggleLangDropdown() {
	const menu = document.getElementById("langMenu");
	menu.hidden = !menu.hidden;
}

function selectLang(lang) {
	cfg.language = lang;
	saveConfig(cfg);
	applyI18n();
	document.getElementById("langMenu").hidden = true;
}

document.addEventListener("click", event => {
	const dropdown = document.getElementById("langDropdown");
	if (!dropdown.contains(event.target)) {
		document.getElementById("langMenu").hidden = true;
	}
});

function hexColorToRgbString(hex) {
	const clean = hex.replace("#", "");
	const bigint = parseInt(clean, 16);
	const red = (bigint >> 16) & 255;
	const green = (bigint >> 8) & 255;
	const blue = bigint & 255;
	return `${red},${green},${blue}`;
}

function updateParaplatformScaleVisibility() {
	const enabled = document.getElementById("paraplatform_enabled").checked;
	const scaleRow = document.getElementById("paraplatformScaleRow");
	if (scaleRow) scaleRow.hidden = !enabled;
}

function updateTracemapColorVisibility() {
	const enabled = document.getElementById("tracemapcolor_enabled").checked;
	const colorRow = document.getElementById("tracemapColorRow");
	if (colorRow) colorRow.hidden = !enabled;
}

function populateForm(formCfg) {
	const form = document.getElementById("configForm");
	for (const [key, value] of Object.entries(formCfg)) {
		const input = form.elements[key];
		if (!input) continue;
		if (input.type == "checkbox") {
			input.checked = !!value;
		} else {
			input.value = value ?? "";
		}
	}
	updateParaplatformScaleVisibility();
	updateTracemapColorVisibility();
}

function readForm() {
	const form = document.getElementById("configForm");
	const result = {};
	for (const element of form.elements) {
		if (!element.name) continue;
		if (element.type == "checkbox") {
			result[element.name] = element.checked;
		} else if (element.type == "number") {
			result[element.name] = element.value == "" ? null : Number(element.value);
		} else {
			result[element.name] = element.value;
		}
	}
	return result;
}

function buildArgs(filePath, currentCfg) {
	const args = ["--video", filePath, "--language", currentCfg.language];

	const startValue = document.getElementById("startTime").value;
	if (startValue != "") args.push("--start", startValue);

	const endValue = document.getElementById("endTime").value;
	if (endValue != "") args.push("--end", endValue);

	args.push("--pool_radius_cm", document.getElementById("poolRadius").value);
	args.push("--mog2_history", String(currentCfg.mog2_history));
	args.push("--mog2_threshold", String(currentCfg.mog2_threshold));
	if (currentCfg.mog2_detect_shadow) args.push("--mog2_detect_shadow");
	args.push("--morph_open_k", String(currentCfg.morph_open_k));
	args.push("--morph_close_k", String(currentCfg.morph_close_k));
	args.push("--min_contour_area", String(currentCfg.min_contour_area));
	args.push("--max_contour_area", String(currentCfg.max_contour_area));
	args.push("--trail_len", String(currentCfg.trail_len));
	args.push("--debug_frames", String(currentCfg.debug_frames));

	if (currentCfg.pool_west) args.push("--pool_west", currentCfg.pool_west);
	if (currentCfg.pool_north) args.push("--pool_north", currentCfg.pool_north);
	if (currentCfg.pool_east) args.push("--pool_east", currentCfg.pool_east);
	if (currentCfg.pool_south) args.push("--pool_south", currentCfg.pool_south);

	if (currentCfg.platform_nw) args.push("--platform_nw", currentCfg.platform_nw);
	if (currentCfg.platform_ne) args.push("--platform_ne", currentCfg.platform_ne);
	if (currentCfg.platform_se) args.push("--platform_se", currentCfg.platform_se);
	if (currentCfg.platform_sw) args.push("--platform_sw", currentCfg.platform_sw);

	if (currentCfg.quadrantcross) args.push("--quadrantcross");
	if (currentCfg.platformcross) args.push("--platformcross");

	if (currentCfg.paraplatform_enabled) {
		const scale = currentCfg.paraplatform_scale ?? 4;
		args.push("--paraplatform", String(scale));
	}

	if (currentCfg.proximity) args.push("--proximity");
	if (currentCfg.latency) args.push("--latency");

	if (currentCfg.tracemapcolor_enabled && currentCfg.tracemapcolor) {
		args.push("--tracemapcolor", hexColorToRgbString(currentCfg.tracemapcolor));
	}

	args.push("--appmode");
	return args;
}

function setUIRunning(running) {
	document.getElementById("selectFileBtn").disabled = running;
	document.getElementById("runBtn").disabled = running || !selectedFile;
	document.getElementById("cancelBtn").disabled = !running;
	document.getElementById("settingsBtn").disabled = running;
	document.getElementById("langBtn").disabled = running;
	document.getElementById("startTime").disabled = running;
	document.getElementById("endTime").disabled = running;
	document.getElementById("poolRadius").disabled = running;
}

function setOutputTabsEnabled(enabled) {
	document.querySelectorAll("#outputTabs .tab").forEach(tab => {
		tab.disabled = !enabled;
	});
	document.getElementById("outputArea").classList.toggle("outputLocked", !enabled);
}

function renderCsvTable(csvText) {
	const lines = csvText.trim().split("\n");
	if (!lines.length) return;
	const headers = lines[0].split(",");
	let html = "<table><thead><tr>";
	for (const header of headers) html += `<th>${header}</th>`;
	html += "</tr></thead><tbody>";
	for (let i = 1; i < lines.length; i++) {
		const cols = lines[i].split(",");
		html += "<tr>";
		for (const col of cols) html += `<td>${col}</td>`;
		html += "</tr>";
	}
	html += "</tbody></table>";
	document.getElementById("csvTable").innerHTML = html;
}

function formatPoint(point) {
	if (!point) return "";
	if (Array.isArray(point)) return point.join(",");
	return String(point);
}

function openSettings() {
	document.getElementById("settingsOverlay").hidden = false;
}

function closeSettings() {
	document.getElementById("settingsOverlay").hidden = true;
	populateForm(cfg);
}

function overlayClose(event) {
	if (event.target == document.getElementById("settingsOverlay")) closeSettings();
}

async function saveSettings(event) {
	event.preventDefault();
	const formData = readForm();
	cfg = { ...cfg, ...formData };
	saveConfig(cfg);
	document.getElementById("settingsOverlay").hidden = true;
}

async function selectFile() {
	try {
		selectedFile = await invoke("pick_file");
		if (selectedFile) {
			document.getElementById("filePath").textContent = selectedFile;
			document.getElementById("runBtn").disabled = false;
		}
	} catch (error) {
		console.log("No file selected:", error);
	}
}

function switchTab(tab) {
	if (tab.disabled) return;
	document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
	document.querySelectorAll(".tabContent").forEach(t => {
		t.hidden = true;
	});
	tab.classList.add("active");
	const tabId = "tab" + tab.dataset.tab.charAt(0).toUpperCase() + tab.dataset.tab.slice(1);
	document.getElementById(tabId).hidden = false;
}

async function runScript() {
	if (!selectedFile) return;

	document.getElementById("progressBar").value = 0;
	document.getElementById("progressText").textContent = "0%";
	document.getElementById("etaText").textContent = "";

	setUIRunning(true);

	const args = buildArgs(selectedFile, cfg);
	pythonProcess = Command.sidecar("bin/main", args);

	pythonProcess.stdout.on("data", async line => {
		let parsed;
		try {
			parsed = JSON.parse(line);
		} catch {
			return;
		}

		if (parsed.progress != undefined) {
			const pct = parsed.progress;
			document.getElementById("progressBar").value = pct;
			document.getElementById("progressText").textContent = `${pct.toFixed(1)}%`;
			document.getElementById("etaText").textContent = parsed.eta > 0 ? `ETA: ${parsed.eta}s` : "";
		}

		if (parsed.done) {
			if (parsed.pool_west) cfg.pool_west = formatPoint(parsed.pool_west);
			if (parsed.pool_north) cfg.pool_north = formatPoint(parsed.pool_north);
			if (parsed.pool_east) cfg.pool_east = formatPoint(parsed.pool_east);
			if (parsed.pool_south) cfg.pool_south = formatPoint(parsed.pool_south);

			if (parsed.platform_nw) cfg.platform_nw = formatPoint(parsed.platform_nw);
			if (parsed.platform_ne) cfg.platform_ne = formatPoint(parsed.platform_ne);
			if (parsed.platform_se) cfg.platform_se = formatPoint(parsed.platform_se);
			if (parsed.platform_sw) cfg.platform_sw = formatPoint(parsed.platform_sw);

			saveConfig(cfg);

			setOutputTabsEnabled(true);

			const firstTab = document.querySelector("#outputTabs .tab");
			if (firstTab) switchTab(firstTab);

			try {
				document.getElementById("tabVideo").hidden = false;
				document.getElementById("videotabbutton").classList.add("active");
				const videoEl = document.getElementById("outputVideo");
				videoEl.src = fileUrl(parsed.video_out);
				videoEl.load();
			} catch (error) {
				console.error("Video load error:", error);
			}

			try {
				renderCsvTable(await fetchText(parsed.csv_out));
			} catch (error) {
				console.error("CSV load error:", error);
			}

			try {
				document.getElementById("summaryText").textContent = await fetchText(parsed.summary_out);
			} catch (error) {
				console.error("Summary load error:", error);
			}

			try {
				document.getElementById("heatmap").style.backgroundImage = `url("${fileUrl(parsed.heatmap_out)}")`;
				document.getElementById("tracemap").style.backgroundImage = `url("${fileUrl(parsed.tracemap_out)}")`;
			} catch (error) {
				console.error("Image load error:", error);
			}

			setUIRunning(false);
		}
	});

	pythonProcess.stderr.on("data", line => {
		console.error("stderr:", line);
	});

	pythonProcess.on("close", code => {
		console.log("Process exited:", code);
		pythonProcess = null;
		setUIRunning(false);
	});

	await pythonProcess.spawn();
}

function cancelScript() {
	if (pythonProcess) {
		pythonProcess.kill();
		pythonProcess = null;
	}
	setUIRunning(false);
	document.getElementById("progressBar").value = 0;
	document.getElementById("progressText").textContent = "—";
	document.getElementById("etaText").textContent = "";
}

document.addEventListener("DOMContentLoaded", () => {
	initFileServer();
	cfg = loadConfig();
	populateForm(cfg);
	applyI18n();
	setUIRunning(false);
	setOutputTabsEnabled(false);
});

window.openSettings = openSettings;
window.closeSettings = closeSettings;
window.overlayClose = overlayClose;
window.saveSettings = saveSettings;
window.updateParaplatformScaleVisibility = updateParaplatformScaleVisibility;
window.updateTracemapColorVisibility = updateTracemapColorVisibility;
window.toggleLangDropdown = toggleLangDropdown;
window.selectLang = selectLang;
window.selectFile = selectFile;
window.switchTab = switchTab;
window.runScript = runScript;
window.cancelScript = cancelScript;
