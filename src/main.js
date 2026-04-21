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
const PROFILES_KEY = "rattracker_profiles";
const ACTIVE_PROFILE_KEY = "rattracker_active_profile";
const DEFAULT_PROFILE_NAME = "Default";

const DEFAULTS = {
	mog2_history_s: 4.0,
	mog2_threshold: 32,
	mog2_detect_shadow: false,
	morph_open_k: 3,
	morph_close_k: 15,
	min_contour_area: 300,
	max_contour_area: 12000,
	trail_s: 2.0,
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
	ratcolor_enabled: false,
	ratcolor: "#ff0000",
	mog2_learning_rate: -1.0,
	max_interp_gap: 0,
	heatmap_sigma: 0,
	language: "en",
};

const I18N = {
	en: {
		title: "Rat Tracker",
		settings: "Settings",
		detection: "Detection",
		mog2_history_s: "MOG2 History (s)",
		mog2_history_s_desc: "Duration in seconds used to build the background model. Higher = slower adaptation, better for stable cameras.",
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
		trail_s: "Trail Length (s)",
		trail_s_desc: "Duration in seconds of the movement trail drawn in the output video. Purely visual.",
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
		ratcolor: "Rat Marker Color",
		ratcolor_desc: "Color of the dot and bounding marker drawn on the rat in the output video.",
		mog2_learning_rate: "MOG2 Learning Rate",
		mog2_learning_rate_desc: "Background adaptation speed. -1 = automatic. Lower values (e.g. 0.001) prevent a slow or stationary rat from being absorbed into the background model, fixing the fast→slow→disappear tracking failure.",
		max_interp_gap: "Max Interpolation Gap (frames)",
		max_interp_gap_desc: "Maximum number of consecutive missing frames to fill by interpolation. 0 = unlimited (old behaviour). Set e.g. 10 to avoid drawing straight lines across the pool during long dropouts.",
		heatmap_sigma: "Heatmap Blur Sigma",
		heatmap_sigma_desc: "Gaussian blur radius for the heatmap output. 0 = auto-calculated from video resolution (recommended). Increase for softer blobs, decrease for sharper.",
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
		mog2_history_s: "Historique MOG2 (s)",
		mog2_history_s_desc: "Durée en secondes pour construire le modèle de fond. Plus élevé = adaptation plus lente, meilleur pour les caméras stables.",
		mog2_threshold: "Seuil MOG2",
		mog2_threshold_desc: "Sensibilité de la détection du premier plan. Plus bas = plus sensible (faux positifs). Plus haut = moins sensible (peut rater le rat).",
		detect_shadows: "Détecter les ombres",
		detect_shadows_desc: "Active la détection d'ombres. Légèrement plus lent mais réduit les artefacts d'ombres confondus avec le rat.",
		morph_open: "Noyau d'ouverture morphologique.",
		morph_open_desc: "Taille du noyau pour supprimer le bruit. Doit être impair. Des valeurs plus grandes suppriment un bruit plus important.",
		morph_close: "Noyau de fermeture morphologique.",
		morph_close_desc: "Taille du noyau pour combler les trous dans le blob détecté. Doit être impair.",
		min_area: "Surface contour min. (px²)",
		min_area_desc: "Taille minimale du blob pour être considéré comme le rat. Augmentez si du bruit est détecté.",
		max_area: "Surface contour max. (px²)",
		max_area_desc: "Taille maximale du blob pour être considéré comme le rat. Diminuez si des reflets sont détectés.",
		trail_s: "Longueur trace (s)",
		trail_s_desc: "Durée en secondes de la trace de mouvement dessinée dans la vidéo de sortie. Purement visuel.",
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
		ratcolor: "Couleur du marqueur rat",
		ratcolor_desc: "Couleur du point et du marqueur dessinés sur le rat dans la vidéo de sortie.",
		mog2_learning_rate: "Taux d'apprentissage MOG2",
		mog2_learning_rate_desc: "Vitesse d'adaptation du fond. -1 = automatique. Des valeurs basses (ex. 0.001) empêchent un rat immobile d'être absorbé dans le fond.",
		max_interp_gap: "Écart d'interpolation max (images)",
		max_interp_gap_desc: "Nombre max d'images manquantes consécutives à interpoler. 0 = illimité. Ex. 10 pour éviter les lignes droites pendant les longues pertes de détection.",
		heatmap_sigma: "Sigma de flou de la carte de chaleur",
		heatmap_sigma_desc: "Rayon du flou gaussien pour la carte de chaleur. 0 = calculé automatiquement selon la résolution (recommandé).",
		save: "Enregistrer",
		cancel: "Annuler",
		select_video: "Choisir une vidéo",
		no_file: "Aucun video sélectionnée",
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
		mog2_history_s: "MOG2 Geçmişi (s)",
		mog2_history_s_desc: "Arka plan modelini oluşturmak için kullanılan süre (saniye). Yüksek = yavaş uyum, sabit kameralar için daha iyi.",
		mog2_threshold: "MOG2 Eşiği",
		mog2_threshold_desc: "Ön plan algılama hassasiyeti. Düşük = daha hassas (yanlış pozitifler). Yüksek = daha az hassas.",
		detect_shadows: "Gölgeleri Algıla",
		detect_shadows_desc: "Gölge tespitini etkinleştirir. Biraz daha yavaş ama gölge artefaktlarını azaltır.",
		morph_open: "Morfoloji Açma Çekirdeği",
		morph_open_desc: "Küçük gürültü bloblarını kaldırmak için kullanılan çekirdek boyutu. Tek sayı olmalı.",
		morph_close: "Morfoloji Kapama Çekirdeği",
		morph_close_desc: "Algılanan fare blobundaki boşlukları doldurmak için çekirdek boyutu. Tek sayı olmalı.",
		min_area: "Min Kontur Alanı (px²)",
		min_area_desc: "Fare olarak kabul edilmek için minimum blob boyutu. Gürültü algılanıyorsa artırın.",
		max_area: "Maks Kontur Alanı (px²)",
		max_area_desc: "Fare olarak kabul edilmek için maksimum blob boyutu. Yansımalar algılanıyorsa azaltın.",
		trail_s: "İz Uzunluğu (s)",
		trail_s_desc: "Çıktı videosunda hareket izi olarak çizilen süre (saniye). Yalnızca görsel.",
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
		quadrantcross_desc: "Farenin her çeyrekten kaç kez çıktığını sayar.",
		platformcross: "Platform Geçişleri",
		platformcross_desc: "Farenin platformdan kaç kez çıktığını sayar. Platform kalibrasyonu gerektirir.",
		paraplatform: "ParaPlatform Analizi",
		paraplatform_desc: "Platform etrafında ölçeklendirilmiş bir bölgede farenin geçirdiği süre ve mesafeyi takip eder.",
		paraplatform_scale: "Alan Ölçek Faktörü",
		paraplatform_scale_desc: "ParaPlatform bölgesi için alan çarpanı. 4 = gerçek platformun 4× alanı.",
		proximity: "Platform Yakınlığı",
		proximity_desc: "Farenin platform merkezine olan ortalama mesafesini hesaplar.",
		latency: "Platform Gecikmesi",
		latency_desc: "Farenin platforma ilk adım atana kadar geçen süre ve mesafeyi kaydeder.",
		tracemapcolor: "Tracemap Rengi",
		tracemapcolor_desc: "Tracemap çıktı görüntüsündeki yol çizgisinin rengi.",
		ratcolor: "Fare İşaret Rengi",
		ratcolor_desc: "Çıktı videosunda fare üzerine çizilen nokta ve işaretin rengi.",
		mog2_learning_rate: "MOG2 Öğrenme Hızı",
		mog2_learning_rate_desc: "Arka plan uyum hızı. -1 = otomatik. Düşük değerler (ör. 0.001) yavaş veya hareketsiz farenin arka plana karışmasını önler.",
		max_interp_gap: "Maks. Enterpolasyon Boşluğu (kare)",
		max_interp_gap_desc: "Enterpolasyonla doldurulacak maksimum ardışık kayıp kare sayısı. 0 = sınırsız. Uzun kayıp dönemlerinde havuz üzerinde düz çizgi çizilmesini önlemek için örn. 10 girin.",
		heatmap_sigma: "Isı Haritası Bulanıklık Sigma",
		heatmap_sigma_desc: "Isı haritası için Gauss bulanıklığı yarıçapı. 0 = çözünürlüğe göre otomatik hesaplanır (önerilen).",
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

function loadProfiles() {
	try {
		const raw = localStorage.getItem(PROFILES_KEY);
		if (raw) {
			const parsed = JSON.parse(raw);
			if (!parsed[DEFAULT_PROFILE_NAME]) parsed[DEFAULT_PROFILE_NAME] = { ...DEFAULTS };
			return parsed;
		}
	} catch {}
	return { [DEFAULT_PROFILE_NAME]: { ...DEFAULTS } };
}

function saveProfiles(p) {
	try {
		localStorage.setItem(PROFILES_KEY, JSON.stringify(p));
	} catch {}
}

function loadActiveProfileName() {
	return localStorage.getItem(ACTIVE_PROFILE_KEY) || DEFAULT_PROFILE_NAME;
}

function saveActiveProfileName(name) {
	localStorage.setItem(ACTIVE_PROFILE_KEY, name);
}

let profiles = loadProfiles();
let activeProfileName = loadActiveProfileName();
if (!profiles[activeProfileName]) activeProfileName = DEFAULT_PROFILE_NAME;

function loadConfig() {
	return { ...DEFAULTS, ...profiles[activeProfileName] };
}

function saveConfig(newCfg) {
	profiles[activeProfileName] = { ...newCfg };
	saveProfiles(profiles);
	try {
		localStorage.setItem(STORAGE_KEY, JSON.stringify(newCfg));
	} catch {}
}

function cfgToShareString(c, profileName = "") {
	const parts = [];
	if (profileName) parts.push(`--profilename "${profileName}"`);
	parts.push(`--mog2_history_s ${c.mog2_history_s}`);
	parts.push(`--mog2_threshold ${c.mog2_threshold}`);
	if (c.mog2_detect_shadow) parts.push("--mog2_detect_shadow");
	parts.push(`--morph_open_k ${c.morph_open_k}`);
	parts.push(`--morph_close_k ${c.morph_close_k}`);
	parts.push(`--min_contour_area ${c.min_contour_area}`);
	parts.push(`--max_contour_area ${c.max_contour_area}`);
	parts.push(`--trail_s ${c.trail_s}`);
	parts.push(`--debug_frames ${c.debug_frames}`);
	if (c.pool_west) parts.push(`--pool_west ${c.pool_west}`);
	if (c.pool_north) parts.push(`--pool_north ${c.pool_north}`);
	if (c.pool_east) parts.push(`--pool_east ${c.pool_east}`);
	if (c.pool_south) parts.push(`--pool_south ${c.pool_south}`);
	if (c.platform_nw) parts.push(`--platform_nw ${c.platform_nw}`);
	if (c.platform_ne) parts.push(`--platform_ne ${c.platform_ne}`);
	if (c.platform_se) parts.push(`--platform_se ${c.platform_se}`);
	if (c.platform_sw) parts.push(`--platform_sw ${c.platform_sw}`);
	if (c.quadrantcross) parts.push("--quadrantcross");
	if (c.platformcross) parts.push("--platformcross");
	if (c.paraplatform_enabled) parts.push(`--paraplatform ${c.paraplatform_scale ?? 4}`);
	if (c.proximity) parts.push("--proximity");
	if (c.latency) parts.push("--latency");
	if (c.tracemapcolor_enabled && c.tracemapcolor) parts.push(`--tracemapcolor ${hexColorToRgbString(c.tracemapcolor)}`);
	if (c.ratcolor_enabled && c.ratcolor) parts.push(`--ratcolor ${hexColorToRgbString(c.ratcolor)}`);
	if (c.mog2_learning_rate != null && c.mog2_learning_rate !== -1.0) parts.push(`--mog2_learning_rate ${c.mog2_learning_rate}`);
	if (c.max_interp_gap != null && c.max_interp_gap !== 0) parts.push(`--max_interp_gap ${c.max_interp_gap}`);
	if (c.heatmap_sigma != null && c.heatmap_sigma !== 0) parts.push(`--heatmap_sigma ${c.heatmap_sigma}`);
	return parts.join(" ");
}

function shareStringToCfg(str) {
	const result = { ...DEFAULTS };
	let profileName = "";
	const tokens = str.trim().split(/\s+/);
	let i = 0;
	while (i < tokens.length) {
		const t = tokens[i],
			next = tokens[i + 1];
		switch (t) {
			case "--profilename": {
				const joined = tokens.slice(i + 1).join(" ");
				const match = joined.match(/^"([^"]+)"/);
				if (match) {
					profileName = match[1];
					const consumed = match[0].split(/\s+/).length;
					i += 1 + consumed;
				} else {
					profileName = next || "";
					i += 2;
				}
				break;
			}
			case "--mog2_history_s":
				result.mog2_history_s = parseFloat(next);
				i += 2;
				break;
			case "--mog2_threshold":
				result.mog2_threshold = parseFloat(next);
				i += 2;
				break;
			case "--mog2_detect_shadow":
				result.mog2_detect_shadow = true;
				i += 1;
				break;
			case "--morph_open_k":
				result.morph_open_k = parseInt(next);
				i += 2;
				break;
			case "--morph_close_k":
				result.morph_close_k = parseInt(next);
				i += 2;
				break;
			case "--min_contour_area":
				result.min_contour_area = parseFloat(next);
				i += 2;
				break;
			case "--max_contour_area":
				result.max_contour_area = parseFloat(next);
				i += 2;
				break;
			case "--trail_s":
				result.trail_s = parseFloat(next);
				i += 2;
				break;
			case "--debug_frames":
				result.debug_frames = parseInt(next);
				i += 2;
				break;
			case "--pool_west":
				result.pool_west = next;
				i += 2;
				break;
			case "--pool_north":
				result.pool_north = next;
				i += 2;
				break;
			case "--pool_east":
				result.pool_east = next;
				i += 2;
				break;
			case "--pool_south":
				result.pool_south = next;
				i += 2;
				break;
			case "--platform_nw":
				result.platform_nw = next;
				i += 2;
				break;
			case "--platform_ne":
				result.platform_ne = next;
				i += 2;
				break;
			case "--platform_se":
				result.platform_se = next;
				i += 2;
				break;
			case "--platform_sw":
				result.platform_sw = next;
				i += 2;
				break;
			case "--quadrantcross":
				result.quadrantcross = true;
				i += 1;
				break;
			case "--platformcross":
				result.platformcross = true;
				i += 1;
				break;
			case "--paraplatform":
				result.paraplatform_enabled = true;
				result.paraplatform_scale = parseInt(next) || 4;
				i += 2;
				break;
			case "--proximity":
				result.proximity = true;
				i += 1;
				break;
			case "--latency":
				result.latency = true;
				i += 1;
				break;
			case "--tracemapcolor":
				result.tracemapcolor_enabled = true;
				result.tracemapcolor = rgbStringToHex(next);
				i += 2;
				break;
			case "--ratcolor":
				result.ratcolor_enabled = true;
				result.ratcolor = rgbStringToHex(next);
				i += 2;
				break;
			case "--mog2_learning_rate":
				result.mog2_learning_rate = parseFloat(next);
				i += 2;
				break;
			case "--max_interp_gap":
				result.max_interp_gap = parseInt(next);
				i += 2;
				break;
			case "--heatmap_sigma":
				result.heatmap_sigma = parseFloat(next);
				i += 2;
				break;
			default:
				i += 1;
		}
	}
	return { result, profileName };
}

function hexColorToRgbString(hex) {
	const clean = hex.replace("#", "");
	const bigint = parseInt(clean, 16);
	return `${(bigint >> 16) & 255},${(bigint >> 8) & 255},${bigint & 255}`;
}

function rgbStringToHex(rgb) {
	const parts = rgb.split(",").map(Number);
	if (parts.length != 3) return "#00ffff";
	return "#" + parts.map(n => n.toString(16).padStart(2, "0")).join("");
}

function renderProfileBar() {
	const select = document.getElementById("profileSelect");
	select.innerHTML = "";
	for (const name of Object.keys(profiles)) {
		const opt = document.createElement("option");
		opt.value = name;
		opt.textContent = name;
		if (name == activeProfileName) opt.selected = true;
		select.appendChild(opt);
	}
	const isDefault = activeProfileName == DEFAULT_PROFILE_NAME;
	document.getElementById("btnRenameProfile").disabled = isDefault;
	document.getElementById("btnDeleteProfile").disabled = isDefault;
}

function switchProfile(name) {
	if (!profiles[name]) return;
	activeProfileName = name;
	saveActiveProfileName(name);
	cfg = loadConfig();
	populateForm(cfg);
	renderProfileBar();
}

function createProfile(name) {
	const trimmed = name.trim();
	if (!trimmed) return;
	profiles[trimmed] = { ...cfg };
	saveProfiles(profiles);
	activeProfileName = trimmed;
	saveActiveProfileName(trimmed);
	renderProfileBar();
}

function renameProfile(newName) {
	const trimmed = newName.trim();
	if (!trimmed || trimmed == activeProfileName || activeProfileName == DEFAULT_PROFILE_NAME) return;
	profiles[trimmed] = profiles[activeProfileName];
	delete profiles[activeProfileName];
	activeProfileName = trimmed;
	saveActiveProfileName(trimmed);
	saveProfiles(profiles);
	renderProfileBar();
}

function deleteProfile() {
	if (activeProfileName == DEFAULT_PROFILE_NAME) return;
	delete profiles[activeProfileName];
	activeProfileName = DEFAULT_PROFILE_NAME;
	saveActiveProfileName(activeProfileName);
	saveProfiles(profiles);
	cfg = loadConfig();
	populateForm(cfg);
	renderProfileBar();
}

function shareProfile() {
	const str = cfgToShareString(cfg, activeProfileName);
	navigator.clipboard.writeText(str).catch(() => {});
	showMiniModal("share", str);
}

function importProfile(str) {
	const { result: imported, profileName: rawName } = shareStringToCfg(str.trim());
	let name = rawName || "Imported Profile";
	let finalName = name;
	let counter = 2;
	while (profiles[finalName]) finalName = `${name} (${counter++})`;
	profiles[finalName] = { ...cfg, ...imported };
	saveProfiles(profiles);
	activeProfileName = finalName;
	saveActiveProfileName(finalName);
	cfg = loadConfig();
	populateForm(cfg);
	renderProfileBar();
}

function showMiniModal(type, prefill = "") {
	const modal = document.getElementById("miniModal");
	const configs = {
		create: { title: "New Profile Name", placeholder: "e.g. Lab A Setup", btn: "Create", readonly: false },
		rename: { title: "Rename Profile", placeholder: "New name…", btn: "Rename", readonly: false },
		import: { title: "Import Profile", placeholder: "Paste share string…", btn: "Import", readonly: false },
		share: { title: "Share Profile", placeholder: "", btn: "Copy", readonly: true },
	};

	const c = configs[type];
	document.getElementById("miniModalTitle").textContent = c.title;
	document.getElementById("miniModalInput").placeholder = c.placeholder;
	document.getElementById("miniModalInput").readOnly = c.readonly;
	document.getElementById("miniModalConfirm").textContent = c.btn;
	document.getElementById("miniModalInput").value = prefill;

	modal.dataset.type = type;
	modal.hidden = false;
	const input = document.getElementById("miniModalInput");
	input.focus();
	input.select();
}

function closeMiniModal() {
	document.getElementById("miniModal").hidden = true;
	document.getElementById("miniModalInput").value = "";
}

function confirmMiniModal() {
	const type = document.getElementById("miniModal").dataset.type;
	const val = document.getElementById("miniModalInput").value;
	if (type == "create" && val.trim()) createProfile(val);
	else if (type == "rename" && val.trim()) renameProfile(val);
	else if (type == "import" && val.trim()) importProfile(val);
	else if (type == "share") navigator.clipboard.writeText(val).catch(() => {});
	closeMiniModal();
}

function translate(key) {
	return I18N[cfg.language]?.[key] ?? I18N.en[key] ?? key;
}

function applyI18n() {
	document.querySelectorAll("[data-i18n]").forEach(el => {
		const key = el.getAttribute("data-i18n");
		const input = el.querySelector("input");
		if (input) el.childNodes[0].textContent = translate(key);
		else el.textContent = translate(key);
	});

	document.querySelectorAll("[data-i18n-desc]").forEach(el => {
		el.textContent = translate(el.getAttribute("data-i18n-desc"));
	});

	if (!selectedFile) document.getElementById("filePath").textContent = translate("no_file");
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
	if (!dropdown.contains(event.target)) document.getElementById("langMenu").hidden = true;
});

function updateParaplatformScaleVisibility() {
	const row = document.getElementById("paraplatformScaleRow");
	if (row) row.hidden = !document.getElementById("paraplatform_enabled").checked;
}

function updateTracemapColorVisibility() {
	const row = document.getElementById("tracemapColorRow");
	if (row) row.hidden = !document.getElementById("tracemapcolor_enabled").checked;
}

function updateRatColorVisibility() {
	const row = document.getElementById("ratColorRow");
	if (row) row.hidden = !document.getElementById("ratcolor_enabled").checked;
}

function populateForm(formCfg) {
	const form = document.getElementById("configForm");
	for (const [key, value] of Object.entries(formCfg)) {
		const input = form.elements[key];
		if (!input) continue;
		if (input.type == "checkbox") input.checked = !!value;
		else input.value = value ?? "";
	}
	updateParaplatformScaleVisibility();
	updateTracemapColorVisibility();
	updateRatColorVisibility();
}

function onFieldChange(element) {
	if (!element.name) return;
	if (element.type == "checkbox") cfg[element.name] = element.checked;
	else if (element.type == "number") cfg[element.name] = element.value == "" ? null : Number(element.value);
	else cfg[element.name] = element.value;
	saveConfig(cfg);

	if (element.name == "paraplatform_enabled") updateParaplatformScaleVisibility();
	if (element.name == "tracemapcolor_enabled") updateTracemapColorVisibility();
	if (element.name == "ratcolor_enabled") updateRatColorVisibility();
}

function attachFormListeners() {
	const form = document.getElementById("configForm");
	for (const element of form.elements) {
		if (!element.name) continue;
		const evt = element.type == "checkbox" || element.type == "color" ? "change" : "input";
		element.addEventListener(evt, () => onFieldChange(element));
	}
}

function buildArgs(filePath, currentCfg) {
	const args = ["--video", filePath, "--language", currentCfg.language];
	const startValue = document.getElementById("startTime").value;
	if (startValue != "") args.push("--start", startValue);
	const endValue = document.getElementById("endTime").value;
	if (endValue != "") args.push("--end", endValue);
	args.push("--pool_radius_cm", document.getElementById("poolRadius").value);
	args.push("--mog2_history_s", String(currentCfg.mog2_history_s));
	args.push("--mog2_threshold", String(currentCfg.mog2_threshold));
	if (currentCfg.mog2_detect_shadow) args.push("--mog2_detect_shadow");
	args.push("--morph_open_k", String(currentCfg.morph_open_k));
	args.push("--morph_close_k", String(currentCfg.morph_close_k));
	args.push("--min_contour_area", String(currentCfg.min_contour_area));
	args.push("--max_contour_area", String(currentCfg.max_contour_area));
	args.push("--trail_s", String(currentCfg.trail_s));
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
	if (currentCfg.paraplatform_enabled) args.push("--paraplatform", String(currentCfg.paraplatform_scale ?? 4));
	if (currentCfg.proximity) args.push("--proximity");
	if (currentCfg.latency) args.push("--latency");
	if (currentCfg.tracemapcolor_enabled && currentCfg.tracemapcolor) args.push("--tracemapcolor", hexColorToRgbString(currentCfg.tracemapcolor));
	if (currentCfg.ratcolor_enabled && currentCfg.ratcolor) args.push("--ratcolor", hexColorToRgbString(currentCfg.ratcolor));
	if (currentCfg.mog2_learning_rate != null && currentCfg.mog2_learning_rate !== -1.0) args.push("--mog2_learning_rate", String(currentCfg.mog2_learning_rate));
	if (currentCfg.max_interp_gap != null && currentCfg.max_interp_gap !== 0) args.push("--max_interp_gap", String(currentCfg.max_interp_gap));
	if (currentCfg.heatmap_sigma != null && currentCfg.heatmap_sigma !== 0) args.push("--heatmap_sigma", String(currentCfg.heatmap_sigma));
	args.push("--appmode");
	return args;
}

function setUIRunning(running) {
	document.getElementById("selectFileBtn").disabled = running;
	document.getElementById("runBtn").disabled = running || !selectedFile;
	document.getElementById("cancelBtn").disabled = !running;
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
	for (const h of headers) html += `<th>${h}</th>`;
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
}

function overlayClose(event) {
	if (event.target == document.getElementById("settingsOverlay")) closeSettings();
}

async function selectFile() {
	try {
		selectedFile = await invoke("pick_file");
		if (selectedFile) {
			document.getElementById("filePath").textContent = selectedFile;
			document.getElementById("runBtn").disabled = false;
		}
	} catch (e) {
		console.log("No file selected:", e);
	}
}

function switchTab(tab) {
	if (tab.disabled) return;

	document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
	document.querySelectorAll(".tabContent").forEach(t => {
		t.hidden = true;
	});

	tab.classList.add("active");
	document.getElementById("tab" + tab.dataset.tab.charAt(0).toUpperCase() + tab.dataset.tab.slice(1)).hidden = false;
}

async function runScript() {
	if (!selectedFile) return;

	document.getElementById("progressBar").value = 0;
	document.getElementById("progressText").textContent = "Launching...";
	document.getElementById("etaText").textContent = "";

	setUIRunning(true);

	let stderrLines = [];
	let completedNormally = false;

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
			completedNormally = true;
			if (parsed.pool_west) cfg.pool_west = formatPoint(parsed.pool_west);
			if (parsed.pool_north) cfg.pool_north = formatPoint(parsed.pool_north);
			if (parsed.pool_east) cfg.pool_east = formatPoint(parsed.pool_east);
			if (parsed.pool_south) cfg.pool_south = formatPoint(parsed.pool_south);
			if (parsed.platform_nw) cfg.platform_nw = formatPoint(parsed.platform_nw);
			if (parsed.platform_ne) cfg.platform_ne = formatPoint(parsed.platform_ne);
			if (parsed.platform_se) cfg.platform_se = formatPoint(parsed.platform_se);
			if (parsed.platform_sw) cfg.platform_sw = formatPoint(parsed.platform_sw);

			saveConfig(cfg);
			populateForm(cfg);
			setOutputTabsEnabled(true);

			const firstTab = document.querySelector("#outputTabs .tab");
			if (firstTab) switchTab(firstTab);

			try {
				document.getElementById("tabVideo").hidden = false;
				document.getElementById("videotabbutton").classList.add("active");
				const videoEl = document.getElementById("outputVideo");
				videoEl.src = fileUrl(parsed.video_out);
				videoEl.load();
			} catch (e) {
				console.error("Video load error:", e);
			}

			try {
				renderCsvTable(await fetchText(parsed.csv_out));
			} catch (e) {
				console.error("CSV load error:", e);
			}

			try {
				document.getElementById("summaryText").textContent = await fetchText(parsed.summary_out);
			} catch (e) {
				console.error("Summary load error:", e);
			}

			try {
				document.getElementById("heatmap").style.backgroundImage = `url("${fileUrl(parsed.heatmap_out)}")`;
				document.getElementById("tracemap").style.backgroundImage = `url("${fileUrl(parsed.tracemap_out)}")`;
			} catch (e) {
				console.error("Image load error:", e);
			}

			setUIRunning(false);
		}
	});

	pythonProcess.stderr.on("data", line => {
		console.error("stderr:", line);
		stderrLines.push(line);
	});

	pythonProcess.on("close", code => {
		console.log("Process exited:", code);
		const wasCancelled = pythonProcess === null;
		pythonProcess = null;
		setUIRunning(false);

		if (!completedNormally && !wasCancelled && code !== 0) {
			showErrorModal(code, stderrLines);
		}
	});
	await pythonProcess.spawn();
}

function cancelScript() {
	if (pythonProcess) {
		const proc = pythonProcess;
		pythonProcess = null;
		proc.kill();
	}
	setUIRunning(false);
	document.getElementById("progressBar").value = 0;
	document.getElementById("progressText").textContent = "";
	document.getElementById("etaText").textContent = "";
}

function showErrorModal(exitCode, stderrLines) {
	document.getElementById("errorModalCode").textContent = `Process exited with code ${exitCode}`;
	const pre = document.getElementById("errorModalStderr");
	pre.textContent = stderrLines.length ? stderrLines.join("\n") : "(no stderr output)";
	document.getElementById("errorModalStderrWrap").open = stderrLines.length > 0;
	document.getElementById("errorModal").hidden = false;
}

function closeErrorModal() {
	document.getElementById("errorModal").hidden = true;
}

document.addEventListener("DOMContentLoaded", () => {
	initFileServer();
	cfg = loadConfig();
	populateForm(cfg);
	applyI18n();
	attachFormListeners();
	renderProfileBar();
	setUIRunning(false);
	setOutputTabsEnabled(false);

	document.getElementById("profileSelect").addEventListener("change", e => switchProfile(e.target.value));
	document.getElementById("miniModalConfirm").addEventListener("click", confirmMiniModal);
	document.getElementById("miniModalCancel").addEventListener("click", closeMiniModal);
	document.getElementById("miniModalInput").addEventListener("keydown", e => {
		if (e.key == "Enter") confirmMiniModal();
		if (e.key == "Escape") closeMiniModal();
	});
	document.getElementById("btnCreateProfile").addEventListener("click", () => showMiniModal("create"));
	document.getElementById("btnRenameProfile").addEventListener("click", () => showMiniModal("rename", activeProfileName));
	document.getElementById("btnDeleteProfile").addEventListener("click", deleteProfile);
	document.getElementById("btnShareProfile").addEventListener("click", shareProfile);
	document.getElementById("btnImportProfile").addEventListener("click", () => showMiniModal("import"));
});

window.openSettings = openSettings;
window.closeSettings = closeSettings;
window.overlayClose = overlayClose;
window.updateParaplatformScaleVisibility = updateParaplatformScaleVisibility;
window.updateTracemapColorVisibility = updateTracemapColorVisibility;
window.updateRatColorVisibility = updateRatColorVisibility;
window.toggleLangDropdown = toggleLangDropdown;
window.selectLang = selectLang;
window.selectFile = selectFile;
window.switchTab = switchTab;
window.runScript = runScript;
window.cancelScript = cancelScript;
window.closeErrorModal = closeErrorModal;
