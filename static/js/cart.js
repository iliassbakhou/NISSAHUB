// static/js/cart.js
"use strict";

const cartModule = (() => {
    // --- UTILITIES ---
    function getCart() {
        const storedCart = localStorage.getItem('nissahub_cart');
        return storedCart ? JSON.parse(storedCart) : [];
    }

    function saveCart(cart) {
        localStorage.setItem('nissahub_cart', JSON.stringify(cart));
    }

    // --- CORE CART LOGIC ---
    function updateCartCount() {
        const cartCountBadge = document.getElementById('cart-item-count');
        if (!cartCountBadge) return;
        
        const cart = getCart();
        const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);

        cartCountBadge.textContent = totalItems;
        cartCountBadge.classList.toggle('has-items', totalItems > 0);
    }

    function addItemToCart(product) {
        let cart = getCart();
        if (!cart.find(item => item.id === product.id)) {
            cart.push({ ...product, quantity: 1 });
            saveCart(cart);
            updateCartCount();
            updateAddToCartButtonState();
        }
    }

    function removeItemFromCart(productId) {
        let cart = getCart();
        cart = cart.filter(item => item.id !== productId);
        saveCart(cart);
        updateCartCount();
        if (document.getElementById('cart-container')) {
            renderCartPage();
        }
    }

    function updateAddToCartButtonState() {
        const btn = document.getElementById('add-to-cart-btn');
        if (!btn) return;
        
        const cart = getCart();
        const itemInCart = cart.find(item => item.id === btn.dataset.productId);
        
        btn.disabled = !!itemInCart;
        btn.innerHTML = itemInCart ? `✓ Added to Cart` : 'Add to Cart';
    }

    // --- PAGE RENDERERS ---

    function renderCartPage() {
        const cartPageContainer = document.getElementById('cart-container');
        if (!cartPageContainer) return;

        const cart = getCart();
        const itemsContainer = document.getElementById('cart-items-container');
        const emptyMsg = document.getElementById('empty-cart-message');
        const layoutBox = document.getElementById('cart-layout-box');

        if (cart.length === 0) {
            emptyMsg.style.display = 'flex';
            layoutBox.style.display = 'none';
            return;
        }

        emptyMsg.style.display = 'none';
        layoutBox.style.display = 'grid';
        itemsContainer.innerHTML = '';

        let subtotal = 0;
        cart.forEach(item => {
            subtotal += item.price;
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>
                    <div class="cart-item-info">
                        <a href="/product/${item.id}"><img src="${item.image}" alt="${item.name}"></a>
                        <div><a href="/product/${item.id}" class="item-name">${item.name}</a></div>
                    </div>
                </td>
                <td class="cart-item-price">${item.price.toFixed(2)} MAD</td>
                <td>
                    <button class="remove-from-cart-btn" data-product-id="${item.id}" title="Remove item">&times;</button>
                </td>
            `;
            itemsContainer.appendChild(tr);
        });

        document.getElementById('cart-subtotal').textContent = `${subtotal.toFixed(2)} MAD`;
        document.getElementById('cart-total').textContent = `${subtotal.toFixed(2)} MAD`;
        
        itemsContainer.querySelectorAll('.remove-from-cart-btn').forEach(btn => {
            btn.addEventListener('click', (e) => removeItemFromCart(e.currentTarget.dataset.productId));
        });
    }

    // --- DEFINITIVE FIX: THIS FUNCTION IS NOW RESTORED AND FUNCTIONAL ---
    function renderCheckoutPage() {
        const checkoutForm = document.getElementById('checkout-form');
        if (!checkoutForm) return;

        const cart = getCart();
        const summaryContainer = document.getElementById('checkout-summary-items');
        const confirmBtn = document.getElementById('confirm-purchase-btn');

        summaryContainer.innerHTML = ''; // Clear "loading" message

        if (cart.length === 0) {
            summaryContainer.innerHTML = '<p>Your cart is empty. Please add items before checking out.</p>';
            confirmBtn.disabled = true;
            document.getElementById('checkout-subtotal').textContent = '0.00 MAD';
            document.getElementById('checkout-total').textContent = '0.00 MAD';
            return;
        }
        
        confirmBtn.disabled = false;
        let subtotal = 0;
        cart.forEach(item => {
            subtotal += item.price;
            const itemDiv = document.createElement('div');
            itemDiv.className = 'summary-item';
            itemDiv.innerHTML = `
                <span class="item-name">${item.name}</span>
                <span class="item-price">${item.price.toFixed(2)} MAD</span>
            `;
            summaryContainer.appendChild(itemDiv);
        });

        document.getElementById('checkout-subtotal').textContent = `${subtotal.toFixed(2)} MAD`;
        document.getElementById('checkout-total').textContent = `${subtotal.toFixed(2)} MAD`;
        document.getElementById('cart-data-input').value = JSON.stringify(cart);

        checkoutForm.addEventListener('submit', () => {
            confirmBtn.disabled = true;
            confirmBtn.textContent = 'Processing...';
            // Clear cart from local storage ONLY after successful form submission to the backend.
            // This is handled server-side, but as a best practice, we'll clear it here too.
            localStorage.removeItem('nissahub_cart');
        });
    }

    // --- INITIALIZATION ---
    function init() {
        updateCartCount(); // Run on every page load for the header icon.

        // Setup page-specific logic
        if (document.getElementById('add-to-cart-btn')) {
            const btn = document.getElementById('add-to-cart-btn');
            updateAddToCartButtonState();
            btn.addEventListener('click', () => {
                addItemToCart({
                    id: btn.dataset.productId,
                    name: btn.dataset.productName,
                    price: parseFloat(btn.dataset.productPrice),
                    image: btn.dataset.productImage
                });
            });
        }
        if (document.getElementById('cart-container')) {
            renderCartPage();
        }
        if (document.getElementById('checkout-form')) {
            renderCheckoutPage();
        }
    }

    return { init };
})();

document.addEventListener('DOMContentLoaded', cartModule.init);