// static/js/main.js
"use strict";

document.addEventListener('DOMContentLoaded', () => {

    // --- Definitive Mobile Navigation Logic ---
    const navOpener = document.getElementById('mobile-nav-opener');
    const navCloser = document.getElementById('mobile-nav-closer');
    const navPanel = document.getElementById('mobile-nav-panel');

    if (navOpener && navPanel && navCloser) {
        const openNav = () => {
            navPanel.classList.add('is-open');
            document.body.style.overflow = 'hidden';
        };
        const closeNav = () => {
            navPanel.classList.remove('is-open');
            document.body.style.overflow = '';
        };
        navOpener.addEventListener('click', openNav);
        navCloser.addEventListener('click', closeNav);
    }

    // --- Definitive User Dropdown Menu Logic ---
    const userMenuButton = document.querySelector('.user-menu-button');
    if (userMenuButton) {
        const dropdown = userMenuButton.closest('.user-menu-dropdown');
        if (dropdown) {
            userMenuButton.addEventListener('click', (event) => {
                event.stopPropagation();
                dropdown.classList.toggle('is-open');
            });
        }
    }
    document.addEventListener('click', (event) => {
        const openDropdown = document.querySelector('.user-menu-dropdown.is-open');
        if (openDropdown && !openDropdown.contains(event.target)) {
            openDropdown.classList.remove('is-open');
        }
    });

    // --- Definitive Creator Storefront Tab Logic ---
    const storefrontNav = document.getElementById('storefront-nav');
    if (storefrontNav) {
        const tabs = storefrontNav.querySelectorAll('.storefront-tab');
        const panels = document.querySelectorAll('.storefront-panel');

        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                tabs.forEach(t => t.classList.remove('active'));
                panels.forEach(p => p.classList.remove('active'));
                tab.classList.add('active');
                const targetPanel = document.querySelector(tab.dataset.tabTarget);
                if (targetPanel) {
                    targetPanel.classList.add('active');
                }
            });
        });
    }

    // --- Full Discussion Feature ---
    const discussionList = document.getElementById('discussion-list');
    const discussionForm = document.getElementById('discussion-form');

    if (discussionForm) {
        discussionForm.addEventListener('submit', function (event) {
            event.preventDefault();
            handleFormSubmission(this, `/skill/${this.dataset.skillId}/discussion`, (data) => {
                const newThread = createThreadElement(data);
                const noPostsMessage = document.getElementById('no-discussions-message');
                if (noPostsMessage) noPostsMessage.remove();
                discussionList.appendChild(newThread);
                this.querySelector('textarea').value = '';
                newThread.scrollIntoView({ behavior: 'smooth', block: 'end' });
            });
        });
    }

    if (discussionList) {
        discussionList.addEventListener('click', function(event) {
            const target = event.target;
            if (target.matches('.reply-btn')) {
                const thread = target.closest('.discussion-thread');
                const replyForm = thread.querySelector('.reply-form');
                replyForm.style.display = replyForm.style.display === 'none' ? 'block' : 'none';
                if(replyForm.style.display === 'block'){
                    replyForm.querySelector('textarea').focus();
                }
            }
            if (target.matches('.delete-post-btn')) handleDelete(target, 'post', `.discussion-thread`);
            if (target.matches('.delete-reply-btn')) handleDelete(target, 'reply', `.discussion-reply`);
        });

        discussionList.addEventListener('submit', function(event) {
            if (!event.target.matches('.reply-form')) return;
            event.preventDefault();
            const form = event.target;
            const postId = form.dataset.postId;
            handleFormSubmission(form, `/skill/${discussionList.dataset.skillId}/discussion/${postId}/reply`, (data) => {
                const repliesContainer = document.getElementById(`replies-for-${postId}`);
                repliesContainer.appendChild(createReplyElement(data, postId));
                form.querySelector('textarea').value = '';
                form.style.display = 'none';
            });
        });
    }

    function handleFormSubmission(formElement, url, onSuccess) {
        const formData = new FormData(formElement);
        const submitButton = formElement.querySelector('button[type="submit"]');
        const originalButtonText = submitButton.textContent;
        submitButton.disabled = true;
        submitButton.textContent = '...';

        fetch(url, { method: 'POST', body: formData })
            .then(res => res.json().then(data => ({ ok: res.ok, data })))
            .then(({ ok, data }) => {
                if (ok && data.status === 'success') {
                    onSuccess(data);
                } else { throw new Error(data.message || 'Failed to submit.'); }
            })
            .catch(err => {
                console.error('Submission error:', err);
                alert(`An error occurred: ${err.message}`);
            })
            .finally(() => {
                submitButton.disabled = false;
                submitButton.textContent = originalButtonText;
            });
    }

    function handleDelete(deleteButton, type, elementToRemoveSelector) {
        if (!confirm(`Are you sure you want to delete this ${type}? This cannot be undone.`)) return;
        const skillId = discussionList.dataset.skillId, postId = deleteButton.dataset.postId, replyId = deleteButton.dataset.replyId;
        let url = `/skill/${skillId}/discussion/${postId}`;
        if (type === 'reply') url += `/reply/${replyId}`;
        
        const elementToRemove = deleteButton.closest(elementToRemoveSelector);
        fetch(url, { method: 'DELETE' })
            .then(res => res.json().then(data => ({ ok: res.ok, data })))
            .then(({ ok, data }) => {
                if (ok && data.status === 'success') {
                    elementToRemove.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                    elementToRemove.style.opacity = '0';
                    elementToRemove.style.transform = 'translateX(-20px)';
                    setTimeout(() => {
                         elementToRemove.remove();
                         if (discussionList.children.length === 0) {
                             const p = document.createElement('p');
                             p.id = 'no-discussions-message';
                             p.className = 'empty-state-message';
                             p.textContent = 'Be the first to start the discussion!';
                             discussionList.appendChild(p);
                         }
                    }, 300);
                } else { throw new Error(data.message || 'Failed to delete.'); }
            })
            .catch(err => {
                console.error('Deletion error:', err);
                alert(`An error occurred: ${err.message}`);
            });
    }

    const SKILL_AUTHOR_ID = discussionList?.dataset.skillAuthorId, CURRENT_USER_ID = discussionList?.dataset.currentUserId;

    function createThreadElement(data) {
        const post = data.post, thread = document.createElement('div'), avatar = data.user_profile.avatar_url || '/static/img/avatar_placeholder.png';
        thread.className = 'discussion-thread';
        thread.id = `thread-${post.id}`;
        thread.innerHTML = `${createPostElement(data).outerHTML}<div class="replies-container" id="replies-for-${post.id}"></div><div class="reply-form-container"><form class="reply-form" data-post-id="${post.id}" style="display: none;"><div class="form-group discussion-input-group"><img class="current-user-avatar" src="${avatar}" alt="Your avatar"><textarea name="content" placeholder="Write a reply..." rows="2" required></textarea><button type="submit" class="btn btn-primary">Reply</button></div></form></div>`;
        return thread;
    }

    function createPostElement(data) {
        const post = data.post, user = data.user_profile, article = document.createElement('article'), canDelete = CURRENT_USER_ID === post.user_id || CURRENT_USER_ID === SKILL_AUTHOR_ID;
        const date = new Date(post.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        const avatar = user.avatar_url || '/static/img/avatar_placeholder.png', displayName = user.displayName || 'Anonymous User';
        article.className = 'discussion-post';
        article.id = `post-${post.id}`;
        article.innerHTML = `<img class="discussion-post-avatar" src="${avatar}" alt="${displayName}'s avatar"><div class="discussion-post-body"><div class="discussion-post-header"><span class="discussion-post-author">${displayName}</span><div class="discussion-meta"><span class="discussion-post-date">${date}</span>${canDelete ? `<button class="delete-post-btn" data-post-id="${post.id}" title="Delete post">🗑️</button>` : ''}</div></div><div class="discussion-post-content"><p>${post.content.replace(/\n/g, '<br>')}</p></div><div class="discussion-post-actions"><button class="btn-link reply-btn">Reply</button></div></div>`;
        return article;
    }

    function createReplyElement(data, postId) {
        const reply = data.reply, user = data.user_profile, article = document.createElement('article'), canDelete = CURRENT_USER_ID === reply.user_id || CURRENT_USER_ID === SKILL_AUTHOR_ID;
        const date = new Date(reply.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        const avatar = user.avatar_url || '/static/img/avatar_placeholder.png', displayName = user.displayName || 'Anonymous User';
        article.className = 'discussion-reply';
        article.id = `reply-${reply.id}`;
        article.innerHTML = `<img class="discussion-post-avatar" src="${avatar}" alt="${displayName}'s avatar"><div class="discussion-post-body"><div class="discussion-post-header"><span class="discussion-post-author">${displayName}</span><div class="discussion-meta"><span class="discussion-post-date">${date}</span>${canDelete ? `<button class="delete-reply-btn" data-post-id="${postId}" data-reply-id="${reply.id}" title="Delete reply">🗑️</button>` : ''}</div></div><div class="discussion-post-content"><p>${reply.content.replace(/\n/g, '<br>')}</p></div></div>`;
        return article;
    }
});