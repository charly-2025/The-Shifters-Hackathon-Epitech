const controls = document.getElementById("controls");
const citiesStore = new Map();
const input = document.querySelector(".search-input");
const suggestionsBox = document.querySelector(".suggestions");
const addBtn = document.querySelector(".add-city-btn");


let selectedCity = null;
function updateControlsVisibility() {
  if (!controls) return;

  if (citiesStore.size === 0) {
    controls.classList.add("hidden");
  } else {
    controls.classList.remove("hidden");
  }
}

function updateSliders() {
  filterCities();
}

const filterButtons = document.querySelectorAll(".filter");
console.log(filterButtons);
let currentFilter = "all";

let select_btn = document.querySelector("#btn-all");
select_btn.classList.add("filter-active");

filterButtons.forEach(button => {
    button.addEventListener("click", () => {
        filterButtons.forEach(b => b.classList.remove("filter-active"));
        button.classList.add("filter-active");

        currentFilter = button.id.replace("btn-", "");
        updateCitiesByFilter(currentFilter);
    });
});


function applyCurrentFilter() {
    updateCitiesByFilter(currentFilter);
}
function cityAlreadyExists(name) {
    return !!document.querySelector(`.city[data-city="${name}"]`);
}

function setAddButtonLoading(isLoading) {
  if (isLoading) {
    addBtn.classList.add("loading");
    addBtn.textContent = "Chargement";
    addBtn.disabled = true;
  } else {
    addBtn.classList.remove("loading");
    addBtn.textContent = "Ajouter";
    addBtn.disabled = false;
  }
}


function create_city_card(){
    let city_card = document.createElement("div");
    city_card.classList.add("city");
    return city_card;
}

function create_city_header(name,dep,hab,sc_global){
    let city_header = document.createElement("div");
    city_header.classList.add("name-stat-grade");

    let city_name_stat = document.createElement("div");
    city_name_stat.classList.add("name-stat");

    let name_city = document.createElement("p");
    name_city.classList.add("open-btn");
    name_city.setAttribute("id","openModal");
    name_city.textContent = name;

    let stat_city = document.createElement("div");
    stat_city.classList.add("stat");

    let loc_city = document.createElement("div");
    loc_city.classList.add("loc");
    loc_city.textContent = dep;

    let hab_city = document.createElement("div");
    hab_city.classList.add("hab");
    hab_city.textContent = hab+" hab.";

    let score_global = document.createElement("div");
    score_global.classList.add("global");
    score_global.textContent=sc_global+"/100";

     if( sc_global < 76 && sc_global > 49){
        score_global.style.color = "#dd891a";
    } else if ( sc_global < 50) {
        score_global.style.color = "#dd4d1a";
    }


    stat_city.appendChild(loc_city);
    stat_city.appendChild(hab_city);

    city_name_stat.appendChild(name_city);
    city_name_stat.appendChild(stat_city);

    city_header.appendChild(city_name_stat);
    city_header.appendChild(score_global);

    return city_header
}


function createGrade(label, score) {
    if (!Number.isFinite(score)) score = 0;
    const grade = document.createElement("div");
    grade.classList.add("grade");

    const name = document.createElement("div");
    name.classList.add("name");

    const labelP = document.createElement("p");
    labelP.textContent = label;

    const scoreP = document.createElement("p");
    scoreP.textContent = score + "/100";

    name.appendChild(labelP);
    name.appendChild(scoreP);

    const jauge = document.createElement("div");
    jauge.classList.add("jauge");

    const jaugeRemplie = document.createElement("div");
    jaugeRemplie.classList.add("jauge-remplie");
    jaugeRemplie.style.width = score + "%";

    if( score < 76 && score > 49){
        jaugeRemplie.style.backgroundColor = "#dd891a";
    } else if ( score < 50) {
        jaugeRemplie.style.backgroundColor = "#ce0b07ff";
    }

    jauge.appendChild(jaugeRemplie);

    grade.appendChild(name);
    grade.appendChild(jauge);

    return grade;
}


function createCityGrades(scores) {
  const fiveGrades = document.createElement("div");
  fiveGrades.classList.add("five-grades");

  fiveGrades.appendChild(createGrade("Consommation d'Electricité", scores.elec));
  fiveGrades.appendChild(createGrade("Espace vert", scores.bio));
  fiveGrades.appendChild(createGrade("Qualité de l'air", scores.sob));

  return fiveGrades;
}



function add_city(name, dep, hab, sc_global, sc_mob, sc_elec, sc_bio, sc_dech, sc_sob) {
  if (cityAlreadyExists(name)) return;

  citiesStore.set(name, {
    dep,
    hab,
    global: sc_global,
    mob: sc_mob,
    elec: sc_elec,
    bio: sc_bio,
    dech: sc_dech,
    sob: sc_sob
  });

  const city_card = create_city_card();
  city_card.dataset.city = name;

  city_card.appendChild(create_city_header(name, dep, hab, sc_global));

const cityScores = {
  mob: sc_mob,
  elec: sc_elec,
  bio: sc_bio,
  dech: sc_dech,
  sob: sc_sob
};

let grades;
if (currentFilter === "all") {
  grades = createCityGrades(cityScores);
} else {
  const { label, key } = filterMap[currentFilter];
  grades = createCityGradesSingle(label, cityScores[key]);
}


  city_card.appendChild(grades);

  const compare_button = document.createElement("button");
  compare_button.classList.add("compare");
  compare_button.textContent = "Sélectionner pour comparer";
  city_card.appendChild(compare_button);

  document.querySelector(".container-city").appendChild(city_card);

  updateSliders(); 
  updateControlsVisibility();

}

function getCitiesForFilter() {
  return Array.from(citiesStore.entries()).map(([name, city]) => {
    return {
      name,
      habitants: city.hab,
      score: city.global,
      element: document.querySelector(`.city[data-city="${name}"]`)
    };
  }).filter(c => c.element);
}


const filterMap = {
    all: null,
    mobil: { label: "Mobilité", key: "mob" },
    ene: { label: "Energie", key: "elec" },
    bio: { label: "Biodiversité", key: "bio" },
    dec: { label: "Déchets", key: "dech" },
    sob: { label: "Sobriété", key: "sob" }
};

function createCityGradesSingle(label, score) {
    const fiveGrades = document.createElement("div");
    fiveGrades.classList.add("five-grades");

    fiveGrades.appendChild(createGrade(label, score));

    const dataDiv = document.createElement("div");
    dataDiv.classList.add("category-data");
    dataDiv.textContent = "Données détaillées à venir";
    dataDiv.style.color = "white";

    fiveGrades.appendChild(dataDiv);

    return fiveGrades;
}



input.addEventListener("input", () => {
  const value = input.value.trim().toLowerCase();
  suggestionsBox.innerHTML = "";
  addBtn.classList.add("hidden");
  selectedCity = null;

  if (value.length < 2) return;

  citySuggestions
    .filter(city => city.toLowerCase().includes(value))
    .slice(0, 10)
    .forEach(city => {
      const item = document.createElement("div");
      item.classList.add("suggestion-item");
      item.textContent = city;

      item.addEventListener("click", () => {
        input.value = city;
        selectedCity = city;
        suggestionsBox.innerHTML = "";
        addBtn.classList.remove("hidden"); // ✅
      });

      suggestionsBox.appendChild(item);
    });
});



document.addEventListener("click", (e) => {
  if (
    !e.target.closest(".search-input") &&
    !e.target.closest(".suggestions")
  ) {
    suggestionsBox.innerHTML = "";
  }
});


addBtn.addEventListener("click", async () => {
  if (!selectedCity) return;

  showPageLoader();

  try {
    const data = await fetchEcoCity(selectedCity);
    const city = mapBackendCityToFrontend(data);

    add_city(
      city.name,
      city.dep,
      city.hab,
      city.global,
      city.mob,
      city.elec,
      city.bio,
      city.dech,
      city.sob
    );
  } catch (err) {
    console.error(err);
    alert("Impossible de récupérer les données de la ville");
  } finally {
    hidePageLoader();

    input.value = "";
    selectedCity = null;
    addBtn.classList.add("hidden");

  }
});


const pageLoader = document.getElementById("page-loader");

function showPageLoader() {
  pageLoader.classList.remove("hidden");
}

function hidePageLoader() {
  pageLoader.classList.add("hidden");
}


const resetBtn = document.querySelector(".reset-btn");
const containerCity = document.querySelector(".container-city");

resetBtn.addEventListener("click", () => {
  containerCity.innerHTML = "";
  citiesStore.clear();
updateControlsVisibility();

});


function updateCitiesByFilter(filterKey) {
  document.querySelectorAll(".city").forEach(cityCard => {
    const cityName = cityCard.dataset.city;
    const city = citiesStore.get(cityName);
    if (!city) return;

    const oldGrades = cityCard.querySelector(".five-grades");

    let newGrades;
    if (filterKey === "all") {
      newGrades = createCityGrades({
        mob: city.mob,
        elec: city.elec,
        bio: city.bio,
        dech: city.dech,
        sob: city.sob
        });
    } else {
      const { label, key } = filterMap[filterKey];
      newGrades = createCityGradesSingle(label, city[key]);
    }

    oldGrades.replaceWith(newGrades);
  });
}


const populationRange = document.getElementById("populationRange");
const populationInput = document.getElementById("populationInput");

const scoreRange = document.getElementById("scoreRange");
const scoreInput = document.getElementById("scoreInput");

function getCitiesForFilter() {
  return Array.from(document.querySelectorAll(".city")).map(city => {
    const hab = Number(city.querySelector(".hab")?.textContent.replace(/\D/g, ""));
    const score = Number(city.querySelector(".global")?.textContent.split("/")[0]);
    return { element: city, habitants: hab, score };
  });
}




function filterCities() {
  if (citiesStore.size === 0) return;
  if (!populationRange || !scoreRange) return;

  const popMax = Number(populationRange.value);
  const scoreMin = Number(scoreRange.value);

  getCitiesForFilter().forEach(city => {
    const show = city.habitants <= popMax && city.score >= scoreMin;
    city.element.style.display = show ? "block" : "none";
  });
}



populationRange.addEventListener("input", () => {
    populationInput.value = populationRange.value;
    filterCities();
});

scoreRange.addEventListener("input", () => {
    scoreInput.value = scoreRange.value;
    filterCities();
});

populationInput.addEventListener("input", () => {
    let v = Number(populationInput.value);
    if (v < 0) v = 0;
    if (v > populationRange.max) v = populationRange.max;

    populationRange.value = v;
    filterCities();
});

scoreInput.addEventListener("input", () => {
    let v = Number(scoreInput.value);
    if (v < 0) v = 0;
    if (v > 100) v = 100;

    scoreRange.value = v;
    filterCities();
});

const cityContainer = document.querySelector(".container-city");






async function fetchEcoCity(city) {
    const response = await fetch(
        `http://127.0.0.1:8000/eco?city=${encodeURIComponent(city)}`
    );
    console.log(response);
    if (!response.ok) {
        throw new Error("Erreur serveur");
    }

    return await response.json();
}

function scoreElectricity(kwhPerHab) {
  if (typeof kwhPerHab !== "number") return null;

  if (kwhPerHab <= 2500) return 95;
  if (kwhPerHab <= 3200) return 85;
  if (kwhPerHab <= 4000) return 70;
  if (kwhPerHab <= 5000) return 55;
  if (kwhPerHab <= 6500) return 40;
  return 25;
}


function scoreBiodiversity(greenSharePct) {
  if (typeof greenSharePct !== "number") return null;

  if (greenSharePct >= 45) return 95;
  if (greenSharePct >= 35) return 85;
  if (greenSharePct >= 25) return 70;
  if (greenSharePct >= 15) return 55;
  if (greenSharePct >= 8) return 40;
  return 25;
}


function scoreAirQuality(pollutants) {
  if (!pollutants || typeof pollutants !== "object") return null;

  const limits = {
    no2: 40,
    pm10: 45,
    pm25: 15,
    o3: 100,
    so2: 40
  };

  let worstRatio = null;

  for (const key in limits) {
    const value = pollutants[key]?.value;

    if (typeof value !== "number") continue;

    const ratio = value / limits[key];

    if (worstRatio === null || ratio > worstRatio) {
      worstRatio = ratio;
    }
  }

  if (worstRatio === null) return null;

  if (worstRatio <= 0.25) return 95;
  if (worstRatio <= 0.5)  return 85;
  if (worstRatio <= 0.75) return 70;
  if (worstRatio <= 1.0)  return 55;
  if (worstRatio <= 1.5)  return 40;
  return 25;
}


function averageScore(scores) {
    const validScores = scores.filter(s => typeof s === "number");

    if (validScores.length === 0) return null;

    const sum = validScores.reduce((a, b) => a + b, 0);
    return Math.round(sum / validScores.length);
}

function mapBackendCityToFrontend(data) {
  const depCode = String(data.commune.departement).padStart(2, "0");
  const depName = departements[depCode] ?? "Département inconnu";

const elecScore = scoreElectricity(data.kwh_per_inhabitant);
const bioScore = scoreBiodiversity(data.green_level?.green_share_pct);
const sobScore = scoreAirQuality(
  data.air_quality?.pollutants
);




  const globalScore = averageScore([
    elecScore,
    bioScore,
    sobScore
  ]);

  return {
    name: data.commune.name,
    dep: `${depCode} · ${depName}`,
    hab: data.population?.value ?? 0,

    global: globalScore ?? 0,
    elec: elecScore ?? 0,
    bio: bioScore ?? 0,
    sob: sobScore ?? 0,

    mob: null,
    dech: null
  };
}


const citySuggestions = [
  "Paris",
  "Marseille",
  "Lyon",
  "Toulouse",
  "Nice",
  "Nantes",
  "Montpellier",
  "Strasbourg",
  "Bordeaux",
  "Lille",

  "Rennes",
  "Reims",
  "Le Havre",
  "Saint-Étienne",
  "Toulon",
  "Grenoble",
  "Dijon",
  "Angers",
  "Nîmes",
  "Villeurbanne",

  "Clermont-Ferrand",
  "Le Mans",
  "Aix-en-Provence",
  "Brest",
  "Tours",
  "Amiens",
  "Limoges",
  "Annecy",
  "Perpignan",
  "Boulogne-Billancourt",

  "Metz",
  "Besançon",
  "Orléans",
  "Rouen",
  "Mulhouse",
  "Caen",
  "Nancy",
  "Saint-Denis",
  "Argenteuil",
  "Montreuil",

  "Roubaix",
  "Tourcoing",
  "Avignon",
  "Poitiers",
  "La Rochelle",
  "Chambéry",
  "Bayonne",
  "Angoulême",
  "Brive-la-Gaillarde",
  "Colmar",

  "Évry",
  "Cergy",
  "Pau",
  "Tarbes",
  "Albi",
  "Castres",
  "Montauban",
  "Cahors",
  "Rodez",
  "Millau",

  "Narbonne",
  "Carcassonne",
  "Sète",
  "Agde",
  "Béziers",
  "Arles",
  "Salon-de-Provence",
  "Martigues",
  "Hyères",
  "Draguignan"
];

populationRange.min = 0;
populationInput.min = 0;

scoreRange.min = 0;
scoreRange.max = 100;
scoreInput.min = 0;
scoreInput.max = 100;

scoreRange.value = 0;
scoreInput.value = 0;

const departements = {
  "01": "Ain",
  "02": "Aisne",
  "03": "Allier",
  "04": "Alpes-de-Haute-Provence",
  "05": "Hautes-Alpes",
  "06": "Alpes-Maritimes",
  "07": "Ardèche",
  "08": "Ardennes",
  "09": "Ariège",
  "10": "Aube",
  "11": "Aude",
  "12": "Aveyron",
  "13": "Bouches-du-Rhône",
  "14": "Calvados",
  "15": "Cantal",
  "16": "Charente",
  "17": "Charente-Maritime",
  "18": "Cher",
  "19": "Corrèze",
  "2A": "Corse-du-Sud",
  "2B": "Haute-Corse",
  "21": "Côte-d'Or",
  "22": "Côtes-d'Armor",
  "23": "Creuse",
  "24": "Dordogne",
  "25": "Doubs",
  "26": "Drôme",
  "27": "Eure",
  "28": "Eure-et-Loir",
  "29": "Finistère",
  "30": "Gard",
  "31": "Haute-Garonne",
  "32": "Gers",
  "33": "Gironde",
  "34": "Hérault",
  "35": "Ille-et-Vilaine",
  "36": "Indre",
  "37": "Indre-et-Loire",
  "38": "Isère",
  "39": "Jura",
  "40": "Landes",
  "41": "Loir-et-Cher",
  "42": "Loire",
  "43": "Haute-Loire",
  "44": "Loire-Atlantique",
  "45": "Loiret",
  "46": "Lot",
  "47": "Lot-et-Garonne",
  "48": "Lozère",
  "49": "Maine-et-Loire",
  "50": "Manche",
  "51": "Marne",
  "52": "Haute-Marne",
  "53": "Mayenne",
  "54": "Meurthe-et-Moselle",
  "55": "Meuse",
  "56": "Morbihan",
  "57": "Moselle",
  "58": "Nièvre",
  "59": "Nord",
  "60": "Oise",
  "61": "Orne",
  "62": "Pas-de-Calais",
  "63": "Puy-de-Dôme",
  "64": "Pyrénées-Atlantiques",
  "65": "Hautes-Pyrénées",
  "66": "Pyrénées-Orientales",
  "67": "Bas-Rhin",
  "68": "Haut-Rhin",
  "69": "Rhône",
  "70": "Haute-Saône",
  "71": "Saône-et-Loire",
  "72": "Sarthe",
  "73": "Savoie",
  "74": "Haute-Savoie",
  "75": "Paris",
  "76": "Seine-Maritime",
  "77": "Seine-et-Marne",
  "78": "Yvelines",
  "79": "Deux-Sèvres",
  "80": "Somme",
  "81": "Tarn",
  "82": "Tarn-et-Garonne",
  "83": "Var",
  "84": "Vaucluse",
  "85": "Vendée",
  "86": "Vienne",
  "87": "Haute-Vienne",
  "88": "Vosges",
  "89": "Yonne",
  "90": "Territoire de Belfort",
  "91": "Essonne",
  "92": "Hauts-de-Seine",
  "93": "Seine-Saint-Denis",
  "94": "Val-de-Marne",
  "95": "Val-d'Oise",
  "971": "Guadeloupe",
  "972": "Martinique",
  "973": "Guyane",
  "974": "La Réunion",
  "976": "Mayotte"
};

document.addEventListener("DOMContentLoaded", () => {
  updateControlsVisibility();
  populationRange.max = 2500000;
  populationRange.value = populationRange.max;
  populationInput.value = populationRange.max;

  scoreRange.value = 0;
  scoreInput.value = 0;
});

let selectedCities = [];

const compareBar = document.getElementById("compareBar");
const compareCount = document.getElementById("compareCount");
const launchCompareBtn = document.getElementById("launchCompare");


function bindCompareButtons() {
    const buttons = document.querySelectorAll(".compare");

    buttons.forEach(btn => {
        if (btn.dataset.bound) return;

        btn.dataset.bound = "true";

        btn.addEventListener("click", () => {
            const city = btn.closest(".city");
            toggleCitySelection(city, btn);
        });
    });
}

function toggleCitySelection(cityEl, btn) {
  const cityName = cityEl.dataset.city;

  const index = selectedCities.indexOf(cityName);

  if (index !== -1) {
    selectedCities.splice(index, 1);
    cityEl.classList.remove("compare-selected");
    btn.textContent = "Sélectionner pour comparer";
  } else {
    if (selectedCities.length >= 3) {
      alert("Maximum 3 villes peuvent être comparées.");
      return;
    }

    selectedCities.push(cityName);
    cityEl.classList.add("compare-selected");
    btn.textContent = "Retirer";
  }

  updateCompareBar();
}



function updateCompareBar() {

    if (selectedCities.length === 0) {
        compareBar.classList.add("hidden");
        return;
    }

    compareBar.classList.remove("hidden");
    compareCount.textContent =
        `${selectedCities.length} ville${selectedCities.length > 1 ? "s" : ""} sélectionnée${selectedCities.length > 1 ? "s" : ""}`;
}


launchCompareBtn.addEventListener("click", () => {
  if (selectedCities.length < 2) {
    alert("Sélectionne au moins 2 villes pour comparer.");
    return;
  }

  console.log("Comparaison :", selectedCities);
  openCompareModal();
});


const cityContainerForCompare = document.querySelector(".container-city");

if (cityContainerForCompare) {

    const observerCompare = new MutationObserver(() => {
        bindCompareButtons();
    });

    observerCompare.observe(cityContainerForCompare, {
        childList: true,
        subtree: false
    });
}

document.addEventListener("DOMContentLoaded", () => {
    bindCompareButtons();
});



const compareModalOverlay = document.getElementById("compareModalOverlay");
const compareContent = document.getElementById("compareContent");
const closeCompareModal = document.getElementById("closeCompareModal");


function extractCityData(cityEl) {

    const name =
        cityEl.querySelector(".name-stat p")?.textContent.trim();

    const global =
        Number(cityEl.querySelector(".global")?.textContent.split("/")[0]);

    const habitants =
        cityEl.querySelector(".hab")?.textContent;

    const categories = {};

    cityEl.querySelectorAll(".five-grades .grade").forEach(grade => {
        const catName =
            grade.querySelector(".name p")?.textContent.trim();

        const value =
            Number(
                grade
                    .querySelector(".name p:last-child")
                    ?.textContent.split("/")[0]
            );

        categories[catName] = value;
    });

    return { name, global, habitants, categories };
}

function openCompareModal() {

    const citiesData = selectedCities.map(name => {
    const cityEl = document.querySelector(`.city[data-city="${name}"]`);
    return extractCityData(cityEl);
  });

    buildCompareModal(citiesData);

    compareModalOverlay.classList.remove("hidden");
}


function buildCompareModal(data) {

    compareContent.innerHTML = "";

    const allCats = Object.keys(data[0].categories);

    const bestByCat = {};

    allCats.forEach(cat => {
        bestByCat[cat] = Math.max(...data.map(c => c.categories[cat]));
    });

    const bestGlobal = Math.max(...data.map(c => c.global));

    data.forEach(city => {

        const div = document.createElement("div");
        div.className = "compare-city";

        if (city.global === bestGlobal) {
            div.classList.add("best");
        }

        let catsHTML = "";

        allCats.forEach(cat => {

            const val = city.categories[cat];
            const best = val === bestByCat[cat];

            catsHTML += `
                <div class="compare-cat ${best ? "best" : ""}">
                    <span>${cat}</span>
                    <strong>${val}/100</strong>
                </div>
            `;
        });

        div.innerHTML = `
            <h3>${city.name}</h3>
            <div class="compare-score-global">⭐ ${city.global}/100</div>
            <p>👥 ${city.habitants}</p>
            ${catsHTML}
        `;

        compareContent.appendChild(div);
    });
}

launchCompareBtn.addEventListener("click", () => {

    if (selectedCities.length < 2) {
        alert("Sélectionne au moins 2 villes.");
        return;
    }

    openCompareModal();
});


closeCompareModal.addEventListener("click", () => {
    compareModalOverlay.classList.add("hidden");
});

compareModalOverlay.addEventListener("click", e => {
    if (e.target === compareModalOverlay) {
        compareModalOverlay.classList.add("hidden");
    }
});
