async function loadSummary() {
    try {
        const response = await fetch("/api/summary");
        const data = await response.json();
 
        document.getElementById("stat-products").textContent = data.products.toLocaleString("en-US");
        document.getElementById("stat-users").textContent = data.users.toLocaleString("en-US");
        document.getElementById("stat-interactions").textContent = data.interactions.toLocaleString("en-US");
        document.getElementById("stat-sellers").textContent = data.sellers.toLocaleString("en-US");
    } catch (error) {
        console.error(error);
    }
}
 
loadSummary();
// ---------- Price & Quality Comparison ----------
 
function money(n) {
    return "Rs. " + Number(n).toLocaleString("en-US");
}
 
async function searchProducts() {
    const q = document.getElementById("compareQuery").value.trim();
    const box = document.getElementById("searchResults");
 
    if (!q) {
        alert("Please type a product name");
        return;
    }
 
    box.innerHTML = "<p>Searching...</p>";
 
    try {
        const response = await fetch("/api/search?q=" + encodeURIComponent(q));
        const items = await response.json();
 
        if (items.length === 0) {
            box.innerHTML = "<p>No products found.</p>";
            document.getElementById("comparisonResult").innerHTML = "";
            return;
        }
 
        box.innerHTML = "";
        items.forEach(item => {
            const row = document.createElement("div");
            row.className = "search-item";
            row.innerHTML =
                (item.image_file ? '<img src="/static/images/' + item.image_file + '">' : "") +
                "<span>" + item.product_name + "</span>";
            row.onclick = () => showOffers(item.product_id);
            box.appendChild(row);
        });
 
        showOffers(items[0].product_id);   // show the first result right away
 
    } catch (error) {
        console.error(error);
        box.innerHTML = "<p>Unable to connect to the server.</p>";
    }
}
 
async function showOffers(productId) {
    const target = document.getElementById("comparisonResult");
    target.innerHTML = "<p>Loading offers...</p>";
 
    try {
        const response = await fetch("/api/offers/" + productId);
        const data = await response.json();
 
        if (!response.ok) {
            target.innerHTML = "<p>" + (data.error || "Product not found") + "</p>";
            return;
        }
 
        const p = data.product;
        const img = p.image_file
            ? '<img class="compare-img" src="/static/images/' + p.image_file + '">'
            : "";
 
        let rows = "";
        data.offers.forEach(o => {
            const stockClass = o.stock === "In Stock" ? "stock-in"
                             : o.stock === "Low Stock" ? "stock-low" : "stock-out";
 
            rows += "<tr" + (o.best ? ' class="best-row"' : "") + ">" +
                "<td>" + o.seller + (o.best ? ' <span class="best-badge">Best Deal</span>' : "") + "</td>" +
                "<td>" + money(o.price) + "</td>" +
                "<td>" + (o.shipping === 0 ? "Free" : money(o.shipping)) + "</td>" +
                "<td>" + money(o.total) + "</td>" +
                "<td>&#9733; " + o.rating.toFixed(1) + " (" + o.reviews + ")</td>" +
                '<td><span class="' + stockClass + '">' + o.stock + "</span></td>" +
                "<td>" + o.quality + "</td>" +
                "</tr>";
        });
 
        const best = data.offers.find(o => o.best);
        const bestBar = best
            ? '<div class="best-offer">Best Offer: <b>' + best.seller + "</b> &nbsp;|&nbsp; Total Cost: <b>" +
              money(best.total) + "</b> &nbsp;|&nbsp; Rating: <b>" + best.rating.toFixed(1) + "</b></div>"
            : "";
 
        target.innerHTML =
            '<div class="compare-header">' + img +
            "<div><h3>" + p.name + "</h3><p>Category: " + p.category + " | Product ID: " + p.product_id + "</p></div></div>" +
            '<table class="compare-table"><thead><tr>' +
            "<th>Seller</th><th>Price</th><th>Shipping</th><th>Total Cost</th><th>Rating</th><th>Stock</th><th>Quality</th>" +
            "</tr></thead><tbody>" + rows + "</tbody></table>" + bestBar;
 
    } catch (error) {
        console.error(error);
        target.innerHTML = "<p>Unable to connect to the server.</p>";
    }
}
 
// pressing Enter in the search box also searches
document.getElementById("compareQuery").addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
        searchProducts();
    }
});
// ---------- Analytics ----------
 
async function loadAnalytics() {
    try {
        const response = await fetch("/api/analytics");
        const d = await response.json();
 
        const colors = ["#168C8C", "#35C6B0", "#3B82F6", "#F59E0B", "#EF4444", "#94A3B8"];
 
        // 1) Top 5 popular products (horizontal bars)
        new Chart(document.getElementById("topChart"), {
            type: "bar",
            data: {
                labels: d.top_products.map(p => p.name),
                datasets: [{
                    data: d.top_products.map(p => p.count),
                    backgroundColor: "#168C8C"
                }]
            },
            options: {
                indexAxis: "y",
                maintainAspectRatio: false,
                plugins: { legend: { display: false } }
            }
        });
 
        // 2) Interactions by category (top 5 + Others)
        const top5 = d.categories.slice(0, 5);
        const others = d.categories.slice(5).reduce((sum, c) => sum + c.count, 0);
        new Chart(document.getElementById("categoryChart"), {
            type: "doughnut",
            data: {
                labels: top5.map(c => c.name).concat(["Others"]),
                datasets: [{
                    data: top5.map(c => c.count).concat([others]),
                    backgroundColor: colors
                }]
            },
            options: {
                maintainAspectRatio: false,
                plugins: { legend: { position: "right" } }
            }
        });
 
        // 3) User activity per day (lines)
        new Chart(document.getElementById("activityChart"), {
            type: "line",
            data: {
                labels: d.daily.map(x => x.day.slice(5)),
                datasets: [
                    { label: "Views", data: d.daily.map(x => x.views), borderColor: "#3B82F6", tension: 0.3, pointRadius: 2 },
                    { label: "Cart additions", data: d.daily.map(x => x.carts), borderColor: "#F59E0B", tension: 0.3, pointRadius: 2 },
                    { label: "Purchases", data: d.daily.map(x => x.purchases), borderColor: "#168C8C", tension: 0.3, pointRadius: 2 }
                ]
            },
            options: { maintainAspectRatio: false }
        });
 
        // 4) Model performance (naya Hybrid model)
        const m = d.model || {};
        const f3 = x => Number(x).toFixed(3);
 
        if (!m.real) {
            document.getElementById("modelBox").innerHTML =
                '<p class="model-note">Results file not found (test_results_warm.csv).</p>';
        } else {
            const syn = m.synthetic, bt = m.backtest;
            document.getElementById("modelBox").innerHTML =
                '<table class="model-table"><thead><tr><th>Metric</th><th>Real users</th><th>Synthetic users (demo)</th></tr></thead><tbody>' +
                "<tr><td>Hit@10 (new items)</td><td>" + f3(m.real.hit_new) + "</td><td>" + (syn ? f3(syn.hit) : "-") + "</td></tr>" +
                "<tr><td>95% interval</td><td>" + f3(m.real.ci_lo) + " - " + f3(m.real.ci_hi) + "</td><td>" +
                    (syn ? f3(syn.ci_lo) + " - " + f3(syn.ci_hi) : "-") + "</td></tr>" +
                "<tr><td>NDCG@10 (new items)</td><td>" + f3(m.real.ndcg) + "</td><td>-</td></tr>" +
                "<tr><td>Users tested</td><td>" + m.real.users + "</td><td>" + (syn ? syn.users : "-") + "</td></tr>" +
                '</tbody></table><p class="model-note">Hybrid model. Test: trained on events before 20 Dec, then we check if ' +
                "products bought from 20 Dec onwards (that the user had never touched) appear in the top 10." +
                (bt ? " Over a rolling backtest of " + bt.users + " users, the hybrid beats popularity by +" +
                      f3(bt.hit_diff[0]) + " hit@10 (95% interval " + f3(bt.hit_diff[1]) + " to " + f3(bt.hit_diff[2]) + ")." : "") +
                " Synthetic numbers are on generated data and are for demo only.</p>";
        }
 
        // 5) All models compared on real users
        let rows = "";
        (d.model_table || []).forEach(r => {
            rows += "<tr" + (r.final ? ' class="current"' : "") + ">" +
                "<td>" + r.model + "</td><td>" + f3(r.hit_old) + "</td><td>" + f3(r.hit_new) +
                " (" + f3(r.ci_lo) + "-" + f3(r.ci_hi) + ")</td><td>" + f3(r.ndcg) + "</td></tr>";
        });
        document.getElementById("modelCompare").innerHTML =
            '<table class="model-table"><thead><tr><th>Model</th><th>Hit@10 (old items allowed)</th><th>Hit@10 (new items)</th><th>NDCG (new)</th></tr></thead><tbody>' +
            rows + '</tbody></table><p class="model-note">Highlighted row = the model this dashboard uses.</p>';
 
    } catch (error) {
        console.error(error);
    }
}
 
loadAnalytics();
// ---------- New Customer (cold start) ----------
 
const selectedCategories = new Set();
 
async function loadCategoryChips() {
    try {
        const response = await fetch("/api/categories");
        const cats = await response.json();
        const box = document.getElementById("categoryChips");
 
        cats.forEach(name => {
            const chip = document.createElement("span");
            chip.className = "chip";
            chip.textContent = name;
 
            chip.onclick = () => {
                if (selectedCategories.has(name)) {
                    selectedCategories.delete(name);
                    chip.classList.remove("selected");
                } else {
                    selectedCategories.add(name);
                    chip.classList.add("selected");
                }
            };
 
            box.appendChild(chip);
        });
    } catch (error) {
        console.error(error);
    }
}
 
// ---------- Cart (demo only: saved in this browser, not in the dataset) ----------
 
let cartIds = [];
try {
    cartIds = JSON.parse(localStorage.getItem("shopsmart_cart") || "[]");
} catch (e) {
    cartIds = [];
}
 
function updateCartCount() {
    const el = document.getElementById("cartCount");
    if (el) {
        el.textContent = cartIds.length;
    }
}
 
function toggleCart(productId, button) {
    const i = cartIds.indexOf(productId);
    if (i === -1) {
        cartIds.push(productId);
    } else {
        cartIds.splice(i, 1);
    }
    try {
        localStorage.setItem("shopsmart_cart", JSON.stringify(cartIds));
    } catch (e) {}
 
    const added = cartIds.includes(productId);
    button.textContent = added ? "✓ Added" : "Add to Cart";
    button.classList.toggle("added", added);
    updateCartCount();
}
 
updateCartCount();
 
// ---------- Product cards + carousel ----------
 
function formatReviews(n) {
    return n >= 1000 ? (n / 1000).toFixed(1) + "k" : String(n);
}
 
function slideCards(id, direction) {
    const track = document.getElementById(id);
    track.scrollBy({ left: direction * track.clientWidth * 0.8, behavior: "smooth" });
}
 
function showCards(list, container) {
    container.innerHTML = "";
 
    if (list.length === 0) {
        container.innerHTML = "<p>No recommendations found.</p>";
        return;
    }
 
    list.forEach(product => {
        const card = document.createElement("div");
        card.className = "pcard";
 
        // badge (Recommended / Popular / Trending / Best Seller / In your cart)
        const badge = document.createElement("span");
        badge.className = "pbadge b-" + product.badge.toLowerCase().replace(/ /g, "-");
        badge.textContent = product.badge;
 
        // picture
        let image;
        if (product.image_file) {
            image = document.createElement("img");
            image.src = "/static/images/" + product.image_file;
            image.alt = product.product_name;
            image.className = "pcard-img";
            image.onerror = function () {
                const fallback = document.createElement("div");
                fallback.className = "pcard-noimg";
                fallback.textContent = "No image";
                image.replaceWith(fallback);
            };
        } else {
            image = document.createElement("div");
            image.className = "pcard-noimg";
            image.textContent = "No image";
        }
 
        const name = document.createElement("h3");
        name.className = "pcard-name";
        name.textContent = product.product_name;
 
        const category = document.createElement("div");
        category.className = "pcard-cat";
        category.textContent = product.main_category || "";
 
        const rating = document.createElement("div");
        rating.className = "pcard-rating";
        rating.innerHTML = product.avg_rating
            ? "<b>&#9733;</b> " + Number(product.avg_rating).toFixed(1) +
              " (" + formatReviews(product.review_count || 0) + ")"
            : "No rating yet";
 
        const price = document.createElement("div");
        price.className = "pcard-price";
        price.textContent = product.price_pkr
            ? "Rs. " + Number(product.price_pkr).toLocaleString("en-US")
            : "Price not available";
 
        const why = document.createElement("div");
        why.className = "pcard-why";
        if (product.reason) {
            why.textContent = product.reason.startsWith("In your cart")
                ? product.reason
                : "Similar to: " + product.reason;
        }
 
        const button = document.createElement("button");
        button.className = "pcard-btn";
        const inCart = cartIds.includes(product.product_id);
        button.textContent = inCart ? "✓ Added" : "Add to Cart";
        button.classList.toggle("added", inCart);
        button.onclick = () => toggleCart(product.product_id, button);
 
        card.append(badge, image, name, category, rating, price, why, button);
        container.appendChild(card);
    });
 
    container.scrollLeft = 0;
}
 
async function getNewUserRecommendations() {
    const container = document.getElementById("newUserContainer");
    const method = document.getElementById("newUserMethod");
    const price = document.getElementById("pricePref").value;
    const cats = Array.from(selectedCategories);
 
    container.innerHTML = "<p>Loading recommendations...</p>";
 
    try {
        const url = "/api/new-user?categories=" + encodeURIComponent(cats.join(",")) +
                    "&price=" + encodeURIComponent(price);
        const response = await fetch(url);
        const data = await response.json();
 
        method.textContent = "Method: " + data.method;
        showCards(data.recommendations, container);
 
    } catch (error) {
        console.error(error);
        container.innerHTML = "<p>Unable to connect to the server.</p>";
    }
}
 
loadCategoryChips();
// ---------- User dashboard (profile + recommendations) ----------
 
function stat(label, value) {
    return '<div class="pstat"><small>' + label + "</small><b>" + value + "</b></div>";
}
 
function showProfile(p, method) {
    const box = document.getElementById("profileBox");
    if (!p) {
        box.innerHTML = "";
        return;
    }
 
    const interests = p.interests.map(i =>
        '<div class="bar-row"><span>' + i.name + '</span><div class="bar"><i style="width:' +
        i.percent + '%"></i></div><b>' + i.percent + "%</b></div>"
    ).join("");
 
    const recent = p.recent.map(r =>
        "<tr><td>" + r.time + "</td><td>" + r.action + "</td><td>" + r.product +
        "</td><td>" + r.category + "</td></tr>"
    ).join("");
 
    const spend = p.avg_spend === null ? "-" : "Rs. " + p.avg_spend.toLocaleString("en-US");
 
    box.innerHTML =
        '<div class="profile-card">' +
            '<div class="profile-top">' +
                '<div class="profile-avatar">U</div>' +
                "<div><h3>" + p.label + "</h3><p>" + p.type +
                " &nbsp;|&nbsp; Customer group: <b>" + p.group + "</b></p></div>" +
            "</div>" +
            '<div class="profile-stats">' +
                stat("Views", p.views) + stat("Added to cart", p.carts) +
                stat("Purchases", p.purchases) + stat("Different products", p.products) +
                stat("Avg purchase", spend) +
            "</div>" +
            '<div class="profile-two">' +
                "<div><h4>Interests</h4>" + interests + "</div>" +
                "<div><h4>Recent activity</h4>" +
                '<table class="model-table"><thead><tr><th>Time</th><th>Action</th><th>Product</th><th>Category</th></tr></thead><tbody>' +
                recent + "</tbody></table></div>" +
            "</div>" +
            '<p class="model-note">Method: ' + method + "</p>" +
        "</div>";
}
 
async function getRecommendations() {
    const userId = document.getElementById("userId").value;
    const container = document.getElementById("recommendationsContainer");
    const profileBox = document.getElementById("profileBox");
 
    if (!userId) {
        alert("Please enter a User ID");
        return;
    }
 
    container.innerHTML = "<p>Loading recommendations...</p>";
    profileBox.innerHTML = "";
 
    try {
        const response = await fetch("/api/user/" + userId);
        const data = await response.json();
 
        if (!response.ok) {
            container.innerHTML = "<p>" + (data.error || "User not found") + "</p>";
            return;
        }
 
        showProfile(data.profile, data.method);
        showCards(data.recommendations, container);
        setCurrentUser(data.profile ? data.profile.label : userId, data.recommendations);
 
    } catch (error) {
        console.error(error);
        container.innerHTML = "<p>Unable to connect to the server.</p>";
 
    }
 
}
 
// ---------- Top bar: search, bell, user pill, logout ----------
 
// the search bar on top uses the same search as "Price & Quality Comparison"
function topSearch(event) {
    event.preventDefault();
    const q = document.getElementById("topSearchInput").value.trim();
    if (!q) {
        return;
    }
    document.getElementById("compareQuery").value = q;
    searchProducts();
    document.getElementById("offers").scrollIntoView({ behavior: "smooth" });
}
 
function goToRecommendations() {
    document.getElementById("recommendations").scrollIntoView({ behavior: "smooth" });
}
 
// shows which customer is loaded, and how many of their cart items are waiting (bell)
function setCurrentUser(label, recommendations) {
    document.getElementById("userPillName").textContent = label;
    document.getElementById("userAvatar").textContent = label.charAt(0).toUpperCase();
    document.getElementById("sideUserName").textContent = label;
    document.getElementById("sideAvatar").textContent = label.charAt(0).toUpperCase();
 
    const waiting = recommendations.filter(r => r.badge === "In your cart").length;
    const badge = document.getElementById("bellBadge");
    badge.textContent = waiting;
    badge.hidden = waiting === 0;
}
 
function logout() {
    document.getElementById("userId").value = "";
    document.getElementById("profileBox").innerHTML = "";
    document.getElementById("recommendationsContainer").innerHTML =
        "<p>Enter your User ID to see recommendations.</p>";
    setCurrentUser("Guest", []);
    window.scrollTo({ top: 0, behavior: "smooth" });
}
 












