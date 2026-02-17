// Switch Game Repository - Reactive Search
(function() {
    'use strict';
    
    let allEntries = [];
    let filteredEntries = [];
    let currentPage = 1;
    let itemsPerPage = 10;
    let sortBy = 'downloads'; // 'name', 'downloads', 'size', or 'recent'
    let autoRefreshInterval = null;
    
    // Auto-refresh configuration
    const AUTO_REFRESH_INTERVAL_MS = 10000; // 10 seconds
    
    // Check if user is moderator or admin
    const isModerator = window.userRole && (window.userRole.isModerator || window.userRole.isAdmin);
    const isAuthenticated = window.userRole && window.userRole.isAuthenticated;
    
    // Helper function to normalize strings for search (replace underscores with spaces)
    function normalizeForSearch(text) {
        return text.toLowerCase().replace(/_/g, ' ');
    }
    
    // DOM Elements
    const searchInput = document.getElementById('search-input');
    const resultsGrid = document.getElementById('results-grid');
    const resultsCount = document.getElementById('results-count');
    const hashCount = document.getElementById('hash-count');
    const loadingState = document.getElementById('loading-state');
    const emptyState = document.getElementById('empty-state');
    const sortSelect = document.getElementById('sort-select');
    
    // Initialize the application
    async function init() {
        // Auto-focus search input
        if (searchInput) {
            searchInput.focus();
        }
        
        // Check URL parameters and apply search query and filter
        const urlParams = new URLSearchParams(window.location.search);
        const searchQuery = urlParams.get('search') || urlParams.get('q');
        const sortParam = urlParams.get('sort');
        
        // Apply sort filter from URL first, then from localStorage if no URL param
        if (sortParam && ['name', 'recent', 'downloads', 'size', 'likes', 'dislikes', 'comments'].includes(sortParam)) {
            sortBy = sortParam;
            if (sortSelect) {
                sortSelect.value = sortBy;
            }
            // Save to localStorage when coming from URL
            localStorage.setItem('preferredSort', sortBy);
        } else {
            // Load from localStorage if no URL parameter
            const savedSort = localStorage.getItem('preferredSort');
            if (savedSort && ['name', 'recent', 'downloads', 'size', 'likes', 'dislikes', 'comments'].includes(savedSort)) {
                sortBy = savedSort;
                if (sortSelect) {
                    sortSelect.value = sortBy;
                }
            }
        }
        
        // Load entries from API
        await loadEntries();
        
        // Apply search query from URL
        if (searchQuery && searchInput) {
            searchInput.value = searchQuery;
            handleSearch({ target: { value: searchQuery } });
        }
        
        // Set up event listeners
        if (searchInput) {
            searchInput.addEventListener('input', handleSearch);
        }
        
        if (sortSelect) {
            sortSelect.addEventListener('change', handleSortChange);
        }
        
        // Start auto-refresh
        startAutoRefresh();
    }
    
    // Load all entries from the API
    async function loadEntries() {
        try {
            showLoading();
            
            // Include sort_by parameter
            const sortParam = sortBy !== 'name' ? `?sort_by=${sortBy}` : '';
            const response = await fetch(`/api/list${sortParam}`);
            if (!response.ok) {
                throw new Error('Failed to fetch entries');
            }
            
            const data = await response.json();
            allEntries = data.entries || [];
            
            // Re-apply current search query if exists
            const searchTerm = searchInput ? searchInput.value.toLowerCase().trim() : '';
            if (searchTerm === '') {
                filteredEntries = allEntries;
            } else {
                filteredEntries = allEntries.filter(entry => {
                    // Normalize both entry name and search term by replacing underscores with spaces
                    return normalizeForSearch(entry.name).includes(normalizeForSearch(searchTerm));
                });
            }
            
            // Re-apply advanced filters if any are active
            applyAdvancedFiltersToResults();
            
            hideLoading();
            renderResults();
            
        } catch (error) {
            console.error('Error loading entries:', error);
            hideLoading();
            showError('Are you signed in? - Failed to load entries. Please try again later.');
        }
    }
    
    // Start auto-refresh
    function startAutoRefresh() {
        // Refresh automatically
        autoRefreshInterval = setInterval(async () => {
            // Silently reload entries in background
            try {
                const sortParam = sortBy !== 'name' ? `?sort_by=${sortBy}` : '';
                const response = await fetch(`/api/list${sortParam}`);
                if (response.ok) {
                    const data = await response.json();
                    allEntries = data.entries || [];
                    
                    // Re-apply current search filter
                    const searchTerm = searchInput ? searchInput.value.toLowerCase().trim() : '';
                    if (searchTerm === '') {
                        filteredEntries = allEntries;
                    } else {
                        filteredEntries = allEntries.filter(entry => {
                            // Normalize both entry name and search term by replacing underscores with spaces
                            return normalizeForSearch(entry.name).includes(normalizeForSearch(searchTerm));
                        });
                    }
                    
                    // Re-apply advanced filters if any are active
                    applyAdvancedFiltersToResults();
                    
                    // Re-render with current page
                    renderResults();
                }
            } catch (error) {
                console.error('Error during auto-refresh:', error);
            }
        }, AUTO_REFRESH_INTERVAL_MS);
    }
    
    // Stop auto-refresh (for cleanup if needed)
    function stopAutoRefresh() {
        if (autoRefreshInterval) {
            clearInterval(autoRefreshInterval);
            autoRefreshInterval = null;
        }
    }
    
    // Handle search input
    function handleSearch(event) {
        const searchTerm = event.target.value.toLowerCase().trim();
        
        if (searchTerm === '') {
            // Show all entries if search is empty
            filteredEntries = allEntries;
        } else {
            // Filter entries by name
            filteredEntries = allEntries.filter(entry => {
                // Normalize both entry name and search term by replacing underscores with spaces
                return normalizeForSearch(entry.name).includes(normalizeForSearch(searchTerm));
            });
        }
        
        // Apply advanced filters if any
        applyAdvancedFiltersToResults();
        
        // Reset to first page when search changes
        currentPage = 1;
        renderResults();
    }
    
    // Apply advanced filters function (called from advanced-filters.js)
    window.applyAdvancedFilters = function(filters) {
        // Re-apply search first
        const searchTerm = searchInput ? searchInput.value.toLowerCase().trim() : '';
        
        if (searchTerm === '') {
            filteredEntries = allEntries;
        } else {
            filteredEntries = allEntries.filter(entry => {
                // Normalize both entry name and search term by replacing underscores with spaces
                return normalizeForSearch(entry.name).includes(normalizeForSearch(searchTerm));
            });
        }
        
        // Apply advanced filters
        applyAdvancedFiltersToResults();
        
        // Reset to first page
        currentPage = 1;
        renderResults();
    };
    
    // Apply advanced filters to current filtered entries
    function applyAdvancedFiltersToResults() {
        const filters = window.getActiveFilters ? window.getActiveFilters() : null;
        if (!filters) return;
        
        // File type filter
        if (filters.fileType !== 'all') {
            filteredEntries = filteredEntries.filter(entry => {
                return entry.file_type && entry.file_type.toLowerCase() === filters.fileType.toLowerCase();
            });
        }
        
        // Size filter
        if (filters.size !== 'all') {
            filteredEntries = filteredEntries.filter(entry => {
                const sizeInGB = entry.size / (1024 * 1024 * 1024);
                
                switch (filters.size) {
                    case 'small':
                        return sizeInGB < 1;
                    case 'medium':
                        return sizeInGB >= 1 && sizeInGB < 5;
                    case 'large':
                        return sizeInGB >= 5 && sizeInGB < 10;
                    case 'xlarge':
                        return sizeInGB >= 10;
                    default:
                        return true;
                }
            });
        }
        
        // Date filter
        if (filters.date !== 'all') {
            const now = new Date();
            filteredEntries = filteredEntries.filter(entry => {
                const dateToCheck = entry.file_modified_at || entry.created_at;
                if (!dateToCheck) return false;
                
                const entryDate = new Date(dateToCheck);
                const diffTime = now - entryDate;
                const diffDays = diffTime / (1000 * 60 * 60 * 24);
                
                switch (filters.date) {
                    case 'today':
                        return diffDays < 1;
                    case 'week':
                        return diffDays < 7;
                    case 'month':
                        return diffDays < 30;
                    case '3months':
                        return diffDays < 90;
                    case 'year':
                        return diffDays < 365;
                    default:
                        return true;
                }
            });
        }
        
        // Downloads filter
        if (filters.downloads !== 'all') {
            filteredEntries = filteredEntries.filter(entry => {
                const downloads = entry.download_count || 0;
                
                switch (filters.downloads) {
                    case 'popular':
                        return downloads >= 100;
                    case 'trending':
                        return downloads >= 50 && downloads < 100;
                    case 'new':
                        return downloads < 50;
                    default:
                        return true;
                }
            });
        }
    }
    
    // Handle sort change
    function handleSortChange(event) {
        sortBy = event.target.value;
        currentPage = 1;
        // Save preference to localStorage
        localStorage.setItem('preferredSort', sortBy);
        loadEntries();
    }
    
    // Render the results
    function renderResults() {
        if (!resultsGrid || !resultsCount) return;
        
        // Update count
        const count = filteredEntries.length;
        resultsCount.textContent = `${count} ${count === 1 ? 'result' : 'results'} found`;
        
        // Update hash count
        if (hashCount) {
            const totalGames = allEntries.length;
            const hashedGames = allEntries.filter(entry => {
                const hasMD5 = entry.md5_hash && entry.md5_hash !== 'processing' && entry.md5_hash !== '';
                const hasSHA256 = entry.sha256_hash && entry.sha256_hash !== 'processing' && entry.sha256_hash !== '';
                return hasMD5 || hasSHA256;
            }).length;
            hashCount.textContent = `🔐 Hashed: ${hashedGames}/${totalGames}`;
        }
        
        // Clear previous results
        resultsGrid.innerHTML = '';
        
        // Show empty state if no results
        if (count === 0) {
            showEmptyState();
            return;
        }
        
        hideEmptyState();
        
        // Calculate pagination
        const totalPages = Math.ceil(count / itemsPerPage);
        const startIndex = (currentPage - 1) * itemsPerPage;
        const endIndex = startIndex + itemsPerPage;
        const paginatedEntries = filteredEntries.slice(startIndex, endIndex);
        
        // Render each result for current page
        paginatedEntries.forEach(entry => {
            const card = createResultCard(entry);
            resultsGrid.appendChild(card);
        });
        
        // Render pagination controls
        renderPagination(totalPages, count);
    }
    
    // Render pagination controls
    function renderPagination(totalPages, totalCount) {
        // Find or create top pagination container
        let topPaginationContainer = document.getElementById('pagination-controls-top');
        if (!topPaginationContainer) {
            topPaginationContainer = document.createElement('div');
            topPaginationContainer.id = 'pagination-controls-top';
            topPaginationContainer.className = 'pagination-container';
            
            // Insert before results grid
            const resultsGrid = document.getElementById('results-grid');
            if (resultsGrid) {
                resultsGrid.parentNode.insertBefore(topPaginationContainer, resultsGrid);
            }
        }
        
        // Find or create bottom pagination container
        let bottomPaginationContainer = document.getElementById('pagination-controls-bottom');
        if (!bottomPaginationContainer) {
            bottomPaginationContainer = document.createElement('div');
            bottomPaginationContainer.id = 'pagination-controls-bottom';
            bottomPaginationContainer.className = 'pagination-container';
            
            // Insert after results grid
            const resultsSection = document.querySelector('.results-section');
            if (resultsSection) {
                resultsSection.appendChild(bottomPaginationContainer);
            }
        }
        
        // Clear existing content
        topPaginationContainer.innerHTML = '';
        bottomPaginationContainer.innerHTML = '';
        
        // Don't show pagination if only one page
        if (totalPages <= 1) {
            return;
        }
        
        // Helper function to create pagination content
        function createPaginationContent(idSuffix) {
            // Create pagination wrapper
            const paginationWrapper = document.createElement('div');
            paginationWrapper.className = 'pagination-wrapper';
            
            // Items per page selector
            const itemsPerPageContainer = document.createElement('div');
            itemsPerPageContainer.className = 'items-per-page-container';
            itemsPerPageContainer.innerHTML = `
                <label for="items-per-page-${idSuffix}">Items per page:</label>
                <select id="items-per-page-${idSuffix}" class="items-per-page-select">
                    <option value="10" ${itemsPerPage === 10 ? 'selected' : ''}>10</option>
                    <option value="25" ${itemsPerPage === 25 ? 'selected' : ''}>25</option>
                    <option value="50" ${itemsPerPage === 50 ? 'selected' : ''}>50</option>
                    <option value="100" ${itemsPerPage === 100 ? 'selected' : ''}>100</option>
                </select>
            `;
            
            // Page info
            const pageInfo = document.createElement('div');
            pageInfo.className = 'page-info';
            const startItem = (currentPage - 1) * itemsPerPage + 1;
            const endItem = Math.min(currentPage * itemsPerPage, totalCount);
            pageInfo.textContent = `Showing ${startItem}-${endItem} of ${totalCount}`;
            
            // Page controls
            const pageControls = document.createElement('div');
            pageControls.className = 'page-controls';
            
            // Previous button
            const prevButton = document.createElement('button');
            prevButton.className = 'page-button';
            prevButton.textContent = '← Previous';
            prevButton.disabled = currentPage === 1;
            prevButton.addEventListener('click', () => {
                if (currentPage > 1) {
                    currentPage--;
                    renderResults();
                    scrollToTop();
                }
            });
            
            // Page numbers
            const pageNumbers = document.createElement('div');
            pageNumbers.className = 'page-numbers';
            
            // Calculate which page numbers to show
            const maxPageButtons = 5;
            let startPage = Math.max(1, currentPage - Math.floor(maxPageButtons / 2));
            let endPage = Math.min(totalPages, startPage + maxPageButtons - 1);
            
            // Adjust start if we're near the end
            if (endPage - startPage < maxPageButtons - 1) {
                startPage = Math.max(1, endPage - maxPageButtons + 1);
            }
            
            // First page button
            if (startPage > 1) {
                const firstButton = createPageButton(1, 1 === currentPage);
                pageNumbers.appendChild(firstButton);
                
                if (startPage > 2) {
                    const ellipsis = document.createElement('span');
                    ellipsis.className = 'page-ellipsis';
                    ellipsis.textContent = '...';
                    pageNumbers.appendChild(ellipsis);
                }
            }
            
            // Page number buttons
            for (let i = startPage; i <= endPage; i++) {
                const pageButton = createPageButton(i, i === currentPage);
                pageNumbers.appendChild(pageButton);
            }
            
            // Last page button
            if (endPage < totalPages) {
                if (endPage < totalPages - 1) {
                    const ellipsis = document.createElement('span');
                    ellipsis.className = 'page-ellipsis';
                    ellipsis.textContent = '...';
                    pageNumbers.appendChild(ellipsis);
                }
                
                const lastButton = createPageButton(totalPages, totalPages === currentPage);
                pageNumbers.appendChild(lastButton);
            }
            
            // Next button
            const nextButton = document.createElement('button');
            nextButton.className = 'page-button';
            nextButton.textContent = 'Next →';
            nextButton.disabled = currentPage === totalPages;
            nextButton.addEventListener('click', () => {
                if (currentPage < totalPages) {
                    currentPage++;
                    renderResults();
                    scrollToTop();
                }
            });
            
            // Assemble page controls
            pageControls.appendChild(prevButton);
            pageControls.appendChild(pageNumbers);
            pageControls.appendChild(nextButton);
            
            // Assemble pagination wrapper
            paginationWrapper.appendChild(itemsPerPageContainer);
            paginationWrapper.appendChild(pageInfo);
            paginationWrapper.appendChild(pageControls);
            
            return paginationWrapper;
        }
        
        // Create and append pagination for both top and bottom
        const topPagination = createPaginationContent('top');
        const bottomPagination = createPaginationContent('bottom');
        
        topPaginationContainer.appendChild(topPagination);
        bottomPaginationContainer.appendChild(bottomPagination);
        
        // Add event listeners for both items per page selectors
        const topItemsPerPageSelect = document.getElementById('items-per-page-top');
        const bottomItemsPerPageSelect = document.getElementById('items-per-page-bottom');
        
        function handleItemsPerPageChange(e) {
            itemsPerPage = parseInt(e.target.value);
            currentPage = 1;
            renderResults();
            scrollToTop();
        }
        
        if (topItemsPerPageSelect) {
            topItemsPerPageSelect.addEventListener('change', handleItemsPerPageChange);
        }
        if (bottomItemsPerPageSelect) {
            bottomItemsPerPageSelect.addEventListener('change', handleItemsPerPageChange);
        }
    }
    
    // Create a page button
    function createPageButton(pageNum, isActive) {
        const button = document.createElement('button');
        button.className = 'page-number-button' + (isActive ? ' active' : '');
        button.textContent = pageNum;
        button.addEventListener('click', () => {
            currentPage = pageNum;
            renderResults();
            scrollToTop();
        });
        return button;
    }
    
    // Scroll to top of results
    function scrollToTop() {
        const resultsSection = document.querySelector('.results-section');
        if (resultsSection) {
            resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }
    
    // Create a result card element
    function createResultCard(entry) {
        const card = document.createElement('div');
        card.className = 'result-card';
        
        // Make card clickable to open info
        card.style.cursor = 'pointer';
        card.addEventListener('click', (e) => {
            // Don't trigger if clicking on action buttons or interactive elements
            if (!e.target.closest('.result-actions') && !e.target.closest('.meta-item-interactive')) {
                showFileInfo(entry);
            }
        });
        
        const title = document.createElement('div');
        title.className = 'result-title';
        title.textContent = entry.name.replace(/_/g, ' ');
        
        const meta = document.createElement('div');
        meta.className = 'result-meta';
        
        // File type badge
        const fileTypeBadge = document.createElement('span');
        fileTypeBadge.className = `file-type-badge file-type-${entry.file_type}`;
        fileTypeBadge.textContent = entry.file_type.toUpperCase();
        
        const fileTypeItem = document.createElement('div');
        fileTypeItem.className = 'meta-item';
        fileTypeItem.appendChild(fileTypeBadge);
        
        // Size
        const sizeItem = document.createElement('div');
        sizeItem.className = 'meta-item';
        sizeItem.innerHTML = `📦 ${formatSize(entry.size)}`;
        
        // File modified date (use file_modified_at if available, otherwise created_at)
        const dateItem = document.createElement('div');
        dateItem.className = 'meta-item';
        const dateToShow = entry.file_modified_at || entry.created_at;
        dateItem.innerHTML = `📅 ${formatDate(dateToShow)}`;
        dateItem.title = entry.file_modified_at ? `File modified: ${dateToShow}` : `Added: ${dateToShow}`;
        
        // Download count
        const downloadItem = document.createElement('div');
        downloadItem.className = 'meta-item';
        const downloadCount = entry.download_count || 0;
        downloadItem.innerHTML = `⬇️ ${downloadCount}`;
        downloadItem.title = `${downloadCount} download${downloadCount !== 1 ? 's' : ''}`;
        
        // Likes count with clickable thumbs up
        const likesItem = document.createElement('div');
        likesItem.className = 'meta-item meta-item-interactive';
        const likesCount = entry.likes_count || 0;
        likesItem.innerHTML = `<span class="vote-button" data-vote="like" title="Like this entry">👍</span> ${likesCount}`;
        likesItem.querySelector('.vote-button').addEventListener('click', (e) => {
            e.stopPropagation();
            handleVote(entry, 'like', e.target);
        });
        
        // Dislikes count with clickable thumbs down
        const dislikesItem = document.createElement('div');
        dislikesItem.className = 'meta-item meta-item-interactive';
        const dislikesCount = entry.dislikes_count || 0;
        dislikesItem.innerHTML = `<span class="vote-button" data-vote="dislike" title="Dislike this entry">👎</span> ${dislikesCount}`;
        dislikesItem.querySelector('.vote-button').addEventListener('click', (e) => {
            e.stopPropagation();
            handleVote(entry, 'dislike', e.target);
        });
        
        // Comment count
        const commentItem = document.createElement('div');
        commentItem.className = 'meta-item';
        const commentCount = entry.comment_count || 0;
        commentItem.innerHTML = `💬 ${commentCount}`;
        commentItem.title = `${commentCount} comment${commentCount !== 1 ? 's' : ''}`;
        
        meta.appendChild(fileTypeItem);
        meta.appendChild(sizeItem);
        meta.appendChild(dateItem);
        meta.appendChild(downloadItem);
        meta.appendChild(likesItem);
        meta.appendChild(dislikesItem);
        meta.appendChild(commentItem);
        
        // Report warning badge if there are open reports
        if (entry.report_count && entry.report_count > 0) {
            const reportBadge = document.createElement('div');
            reportBadge.className = 'report-warning-badge';
            reportBadge.innerHTML = `⚠️ ${entry.report_count} report${entry.report_count !== 1 ? 's' : ''}`;
            reportBadge.title = 'This file has been reported as broken or corrupted';
            card.appendChild(reportBadge);
        }
        
        // Action buttons container
        const actions = document.createElement('div');
        actions.className = 'result-actions';
        
        // Download button
        const downloadBtn = document.createElement('button');
        downloadBtn.className = 'btn-download';
        downloadBtn.textContent = '⬇️ Download';
        downloadBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            handleDownload(entry);
        });
        
        // Info button
        const infoBtn = document.createElement('button');
        infoBtn.className = 'btn-info';
        infoBtn.textContent = 'ℹ️ Info';
        infoBtn.title = 'View detailed information';
        infoBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            showFileInfo(entry);
        });
        
        // Report button
        const reportBtn = document.createElement('button');
        reportBtn.className = 'btn-report';
        reportBtn.textContent = '⚠️ Report';
        reportBtn.title = 'Report this file as broken or corrupted';
        reportBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            handleReport(entry);
        });
        
        // Comments button
        const commentsBtn = document.createElement('button');
        commentsBtn.className = 'btn-comments';
        commentsBtn.textContent = '💬 Comments';
        commentsBtn.title = 'View and add comments';
        commentsBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            showComments(entry);
        });
        
        // Send to Switch button (only for authenticated users)
        if (isAuthenticated) {
            const sendToSwitchBtn = document.createElement('button');
            sendToSwitchBtn.className = 'btn-send-switch';
            sendToSwitchBtn.textContent = '📤 Send to Switch';
            sendToSwitchBtn.title = 'Send this game to your Switch via Sphaira';
            sendToSwitchBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                handleSendToSwitch(entry);
            });
            actions.appendChild(sendToSwitchBtn);
        }
        
        actions.appendChild(downloadBtn);
        actions.appendChild(infoBtn);
        actions.appendChild(reportBtn);
        actions.appendChild(commentsBtn);
        
        // Add delete button for moderators/admins
        if (isModerator) {
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'btn-delete';
            deleteBtn.textContent = '🗑️';
            deleteBtn.title = 'Delete this entry (Moderator)';
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                handleDelete(entry);
            });
            actions.appendChild(deleteBtn);
        }
        
        card.appendChild(title);
        card.appendChild(meta);
        card.appendChild(actions);
        
        return card;
    }
    
    // Handle download of an entry
    function handleDownload(entry) {
        // For URLs, open in a new window to trigger download
        if (entry.type === 'url') {
            window.open(entry.source, '_blank');
        } else {
            // For filepaths, use the download API endpoint
            const downloadUrl = `/api/download/${encodeURIComponent(entry._key)}`;
            window.location.href = downloadUrl;
        }
    }
    
    // Show detailed file information
    async function showFileInfo(entry) {
        // Fetch the latest entry information from the server
        try {
            const response = await fetch(`/api/entries/${encodeURIComponent(entry._key)}/info`);
            const data = await response.json();
            
            if (data.success && data.entry) {
                // Use the fresh data from the server
                entry = data.entry;
            }
        } catch (error) {
            console.error('Failed to fetch latest entry info:', error);
            // Continue with the existing entry data if fetch fails
        }
        
        const modal = document.createElement('div');
        modal.className = 'info-modal-overlay';
        
        // Format dates
        const addedDate = entry.created_at ? formatFullDate(entry.created_at) : 'N/A';
        const fileCreated = entry.file_created_at ? formatFullDate(entry.file_created_at) : 'N/A';
        const fileModified = entry.file_modified_at ? formatFullDate(entry.file_modified_at) : 'N/A';
        
        // Check if hashes exist or are being processed
        const hasMD5 = isHashValid(entry.md5_hash);
        const hasSHA256 = isHashValid(entry.sha256_hash);
        const isProcessing = entry.md5_hash === 'processing' || entry.sha256_hash === 'processing';
        const canComputeHashes = entry.type === 'filepath';
        
        modal.innerHTML = `
            <div class="info-modal">
                <div class="info-modal-header">
                    <h3>📋 File Information</h3>
                    <button class="modal-close" onclick="this.closest('.info-modal-overlay').remove()">✕</button>
                </div>
                <div class="info-modal-body">
                    <h4 class="info-file-name">${entry.name.replace(/_/g, ' ')}</h4>
                    
                    <div class="info-section">
                        <div class="info-row">
                            <span class="info-label">File Type:</span>
                            <span class="info-value">
                                <span class="file-type-badge file-type-${entry.file_type}">${entry.file_type.toUpperCase()}</span>
                            </span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">File Size:</span>
                            <span class="info-value">${formatSize(entry.size)}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Downloads:</span>
                            <span class="info-value">${entry.download_count || 0} times</span>
                        </div>
                        ${entry.report_count > 0 ? `
                        <div class="info-row warning">
                            <span class="info-label">⚠️ Reports:</span>
                            <span class="info-value">${entry.report_count} open report${entry.report_count !== 1 ? 's' : ''}</span>
                        </div>
                        ` : ''}
                    </div>
                    
                    <div class="info-section">
                        <h5>📅 Dates</h5>
                        <div class="info-row">
                            <span class="info-label">Added to Library:</span>
                            <span class="info-value">${addedDate}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">File Created:</span>
                            <span class="info-value">${fileCreated}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Last Modified:</span>
                            <span class="info-value">${fileModified}</span>
                        </div>
                    </div>
                    
                    <div class="info-section">
                        <h5>🔐 File Hashes</h5>
                        <div id="hash-section-${entry._key}">
                            ${isProcessing ? `
                            <div class="info-row">
                                <span class="info-label">MD5:</span>
                                <span class="info-value"><em>Processing...</em></span>
                            </div>
                            <div class="info-row">
                                <span class="info-label">SHA256:</span>
                                <span class="info-value"><em>Processing...</em></span>
                            </div>
                            <div class="info-row">
                                <span class="info-value" style="color: #5a9fd4;">⏳ Hash computation in progress. Please wait...</span>
                            </div>
                            ${canComputeHashes ? `
                            <div class="info-row" style="margin-top: 10px;">
                                <button class="btn-compute-hash" onclick="computeHashes('${entry._key}')">🔐 Recheck Hashes</button>
                            </div>
                            ` : ''}
                            ` : hasMD5 || hasSHA256 ? `
                            ${hasMD5 ? `
                            <div class="info-row">
                                <span class="info-label">MD5:</span>
                                <span class="info-value hash-value">${entry.md5_hash}</span>
                            </div>
                            ` : ''}
                            ${hasSHA256 ? `
                            <div class="info-row">
                                <span class="info-label">SHA256:</span>
                                <span class="info-value hash-value">${entry.sha256_hash}</span>
                            </div>
                            ` : ''}
                            ${canComputeHashes ? `
                            <div class="info-row" style="margin-top: 10px;">
                                <button class="btn-compute-hash" onclick="computeHashes('${entry._key}')">🔐 Recompute Hashes</button>
                            </div>
                            ` : ''}
                            ` : `
                            <div class="info-row">
                                <span class="info-value">
                                    ${canComputeHashes ? 
                                        '<button class="btn-compute-hash" onclick="computeHashes(\'' + entry._key + '\')">🔐 Compute Hashes</button>' :
                                        'Hashes not available for URL entries'
                                    }
                                </span>
                            </div>
                            `}
                        </div>
                    </div>
                    
                    ${entry.created_by ? `
                    <div class="info-section">
                        <h5>👤 Uploader</h5>
                        <div class="info-row">
                            <span class="info-label">Added By:</span>
                            <span class="info-value">${entry.created_by}</span>
                        </div>
                    </div>
                    ` : ''}
                    
                    ${entry.metadata && Object.keys(entry.metadata).length > 0 ? `
                    <div class="info-section">
                        <h5>🔧 Additional Details</h5>
                        ${entry.metadata.original_filename ? `
                        <div class="info-row">
                            <span class="info-label">Filename:</span>
                            <span class="info-value small">${entry.metadata.original_filename}</span>
                        </div>
                        ` : ''}
                        ${entry.metadata.directory ? `
                        <div class="info-row">
                            <span class="info-label">Directory:</span>
                            <span class="info-value small">${entry.metadata.directory}</span>
                        </div>
                        ` : ''}
                    </div>
                    ` : ''}
                    
                    <div class="info-actions">
                        <button class="btn-download-full" onclick="document.getElementById('download-${entry._key}').click()">
                            ⬇️ Download This File
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // If hashes are processing, start polling for updates
        if (isProcessing) {
            setTimeout(() => pollForHashes(entry._key), 3000);
        }
        
        // Add hidden download trigger
        const downloadTrigger = document.createElement('a');
        downloadTrigger.id = `download-${entry._key}`;
        downloadTrigger.style.display = 'none';
        downloadTrigger.onclick = () => {
            handleDownload(entry);
            modal.remove();
        };
        document.body.appendChild(downloadTrigger);
    }
    
    // Compute hashes for a file
    window.computeHashes = async function(entryId) {
        const hashSection = document.getElementById(`hash-section-${entryId}`);
        if (!hashSection) return;
        
        // Show loading state immediately
        hashSection.innerHTML = `
            <div class="info-row">
                <span class="info-label">MD5:</span>
                <span class="info-value"><em>Processing...</em></span>
            </div>
            <div class="info-row">
                <span class="info-label">SHA256:</span>
                <span class="info-value"><em>Processing...</em></span>
            </div>
            <div class="info-row">
                <span class="info-value" style="color: #5a9fd4;">⏳ Hash computation in progress. Please wait...</span>
            </div>
        `;
        
        try {
            const response = await fetch(`/api/entries/${encodeURIComponent(entryId)}/hashes`);
            const data = await response.json();
            
            if (data.success) {
                // Check if hashes are ready or still processing
                if (data.processing) {
                    // Hashes are being computed in background, start polling for results
                    setTimeout(() => pollForHashes(entryId), 3000);
                } else if (data.md5 && data.sha256) {
                    // Hashes are ready
                    hashSection.innerHTML = `
                        ${data.cached ? '<div class="info-row"><span class="info-value" style="color: #5a9fd4;">✓ Retrieved from cache</span></div>' : ''}
                        <div class="info-row">
                            <span class="info-label">MD5:</span>
                            <span class="info-value hash-value">${data.md5}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">SHA256:</span>
                            <span class="info-value hash-value">${data.sha256}</span>
                        </div>
                        <div class="info-row" style="margin-top: 10px;">
                            <button class="btn-compute-hash" onclick="computeHashes('${entryId}')">🔐 Recompute Hashes</button>
                        </div>
                    `;
                }
            } else {
                hashSection.innerHTML = `
                    <div class="info-row warning">
                        <span class="info-value">✗ Error: ${data.error}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-value">
                            <button class="btn-compute-hash" onclick="computeHashes('${entryId}')">🔐 Try Again</button>
                        </span>
                    </div>
                `;
            }
        } catch (error) {
            hashSection.innerHTML = `
                <div class="info-row warning">
                    <span class="info-value">✗ Failed to compute hashes</span>
                </div>
                <div class="info-row">
                    <span class="info-value">
                        <button class="btn-compute-hash" onclick="computeHashes('${entryId}')">🔐 Try Again</button>
                    </span>
                </div>
            `;
        }
    };
    
    // Poll for hash computation results
    async function pollForHashes(entryId, attempts = 0) {
        const hashSection = document.getElementById(`hash-section-${entryId}`);
        if (!hashSection) return;
        
        // Stop polling after 60 attempts at 3-second intervals (3 minutes)
        if (attempts >= 60) {
            hashSection.innerHTML = `
                <div class="info-row warning">
                    <span class="info-value">⏱ Hash computation is taking longer than expected. Please click Info again to check status.</span>
                </div>
                <div class="info-row">
                    <span class="info-value">
                        <button class="btn-compute-hash" onclick="computeHashes('${entryId}')">🔐 Check Again</button>
                    </span>
                </div>
            `;
            return;
        }
        
        try {
            // Fetch updated entry info to get latest hash status
            const response = await fetch(`/api/entries/${encodeURIComponent(entryId)}/info`);
            const data = await response.json();
            
            if (data.success && data.entry) {
                const entry = data.entry;
                const hasMD5 = isHashValid(entry.md5_hash);
                const hasSHA256 = isHashValid(entry.sha256_hash);
                const isProcessing = entry.md5_hash === 'processing' || entry.sha256_hash === 'processing';
                
                if (hasMD5 && hasSHA256) {
                    // Hashes are ready
                    hashSection.innerHTML = `
                        <div class="info-row">
                            <span class="info-value" style="color: #5a9fd4;">✓ Hashes computed successfully!</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">MD5:</span>
                            <span class="info-value hash-value">${entry.md5_hash}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">SHA256:</span>
                            <span class="info-value hash-value">${entry.sha256_hash}</span>
                        </div>
                        <div class="info-row" style="margin-top: 10px;">
                            <button class="btn-compute-hash" onclick="computeHashes('${entryId}')">🔐 Recompute Hashes</button>
                        </div>
                    `;
                } else if (isProcessing) {
                    // Still processing, update the display and poll again
                    hashSection.innerHTML = `
                        <div class="info-row">
                            <span class="info-label">MD5:</span>
                            <span class="info-value"><em>Processing...</em></span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">SHA256:</span>
                            <span class="info-value"><em>Processing...</em></span>
                        </div>
                        <div class="info-row">
                            <span class="info-value" style="color: #5a9fd4;">⏳ Hash computation in progress (${attempts + 1}/60)...</span>
                        </div>
                        <div class="info-row" style="margin-top: 10px;">
                            <button class="btn-compute-hash" onclick="computeHashes('${entryId}')">🔐 Recheck Hashes</button>
                        </div>
                    `;
                    setTimeout(() => pollForHashes(entryId, attempts + 1), 3000);
                } else {
                    // Something went wrong, hashes should be available but aren't
                    hashSection.innerHTML = `
                        <div class="info-row warning">
                            <span class="info-value">⚠ Hash computation may have failed</span>
                        </div>
                        <div class="info-row">
                            <span class="info-value">
                                <button class="btn-compute-hash" onclick="computeHashes('${entryId}')">🔐 Try Again</button>
                            </span>
                        </div>
                    `;
                }
            } else {
                // Continue polling on error
                setTimeout(() => pollForHashes(entryId, attempts + 1), 3000);
            }
        } catch (error) {
            // Log error but continue polling
            console.error('Error polling for hashes:', error);
            setTimeout(() => pollForHashes(entryId, attempts + 1), 3000);
        }
    }

    
    // Format full date
    function formatFullDate(dateString) {
        if (!dateString) return 'N/A';
        
        try {
            const date = new Date(dateString);
            return date.toLocaleString('en-US', {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch (error) {
            return dateString;
        }
    }
    
    // Handle report of an entry
    function handleReport(entry) {
        // Create modal for report submission
        const modal = document.createElement('div');
        modal.className = 'report-modal-overlay';
        modal.innerHTML = `
            <div class="report-modal">
                <div class="report-modal-header">
                    <h3>Report File Issue</h3>
                    <button class="modal-close" onclick="this.closest('.report-modal-overlay').remove()">✕</button>
                </div>
                <div class="report-modal-body">
                    <p><strong>File:</strong> ${entry.name.replace(/_/g, ' ')}</p>
                    <form id="report-form">
                        <div class="form-group">
                            <label for="report-reason">Reason:</label>
                            <select id="report-reason" name="reason" required class="form-select">
                                <option value="">Select a reason...</option>
                                <option value="not_working">File Not Working</option>
                                <option value="corrupted">File Corrupted</option>
                                <option value="wrong_file">Wrong File</option>
                                <option value="missing_updates">Missing Updates/DLC</option>
                                <option value="other">Other</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="report-description">Additional Details (Optional):</label>
                            <textarea id="report-description" name="description" rows="4" 
                                class="form-textarea" placeholder="Describe the issue..."></textarea>
                        </div>
                        <div class="form-actions">
                            <button type="button" class="btn-cancel" onclick="this.closest('.report-modal-overlay').remove()">
                                Cancel
                            </button>
                            <button type="submit" class="btn-submit">Submit Report</button>
                        </div>
                    </form>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Handle form submission
        const form = modal.querySelector('#report-form');
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const formData = new FormData(form);
            formData.append('entry_id', entry._key);
            formData.append('entry_name', entry.name);
            
            const submitBtn = form.querySelector('.btn-submit');
            submitBtn.disabled = true;
            submitBtn.textContent = 'Submitting...';
            
            try {
                const response = await fetch('/api/reports/submit', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.success) {
                    Toast.success('Report submitted successfully. Thank you for helping improve our collection!');
                    setTimeout(() => {
                        modal.remove();
                        // Reload entries to update report counts
                        loadEntries();
                    }, 1500);
                } else {
                    Toast.error(data.error || 'Failed to submit report');
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Submit Report';
                }
            } catch (error) {
                Toast.error('Error submitting report. Please try again.');
                submitBtn.disabled = false;
                submitBtn.textContent = 'Submit Report';
            }
        });
    }
    
    // Handle send to switch
    async function handleSendToSwitch(entry) {
        try {
            const response = await fetch('/api/send-to-switch', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin',
                body: JSON.stringify({
                    entry_id: entry._key
                })
            });
            
            if (response.status === 401) {
                Toast.error('Authentication required. Please log in.');
                return;
            }
            
            const data = await response.json();
            
            if (data.success) {
                Toast.success(`${entry.name.replace(/_/g, ' ')} has been added to your Send to Switch queue!`);
            } else {
                Toast.error(data.error || 'Failed to add to queue');
            }
        } catch (error) {
            console.error('Error sending to switch:', error);
            Toast.error('Error adding to queue. Please try again.');
        }
    }
    
    // Handle delete of an entry (moderator only)
    async function handleDelete(entry) {
        // Create confirmation modal
        const modal = document.createElement('div');
        modal.className = 'report-modal-overlay';
        modal.innerHTML = `
            <div class="report-modal">
                <div class="report-modal-header">
                    <h3>⚠️ Delete Entry</h3>
                    <button class="modal-close" onclick="this.closest('.report-modal-overlay').remove()">✕</button>
                </div>
                <div class="report-modal-body">
                    <p><strong>File:</strong> ${entry.name.replace(/_/g, ' ')}</p>
                    <p style="color: #ef4444; margin-top: 15px;">
                        <strong>Warning:</strong> This will permanently delete the entry and remove the file from disk. 
                        This action cannot be undone!
                    </p>
                    <div class="form-actions" style="margin-top: 20px;">
                        <button type="button" class="btn-cancel" onclick="this.closest('.report-modal-overlay').remove()">
                            Cancel
                        </button>
                        <button type="button" class="btn-delete-confirm" style="background: #ef4444;">
                            🗑️
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Handle delete confirmation
        const deleteBtn = modal.querySelector('.btn-delete-confirm');
        deleteBtn.addEventListener('click', async () => {
            deleteBtn.disabled = true;
            deleteBtn.textContent = 'Deleting...';
            
            try {
                const response = await fetch(`/api/entries/${encodeURIComponent(entry._key)}/delete`, {
                    method: 'POST'
                });
                
                const data = await response.json();
                
                if (data.success) {
                    Toast.success('Entry deleted successfully');
                    modal.remove();
                    // Reload entries to reflect deletion
                    await loadEntries();
                } else {
                    Toast.error(data.error || 'Failed to delete entry');
                    deleteBtn.disabled = false;
                    deleteBtn.textContent = '🗑️';
                }
            } catch (error) {
                Toast.error('Error deleting entry. Please try again.');
                deleteBtn.disabled = false;
                deleteBtn.textContent = '🗑️';
            }
        });
    }
    
    // Handle vote (like/dislike) on an entry
    async function handleVote(entry, voteType, button) {
        try {
            button.disabled = true;
            
            const formData = new FormData();
            formData.append('vote_type', voteType);
            
            const response = await fetch(`/api/entries/${encodeURIComponent(entry._key)}/vote`, {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Check if vote was added or removed based on user_vote in response
                const action = data.user_vote === voteType ? 'added' : 'removed';
                const message = action === 'added' 
                    ? `${voteType === 'like' ? 'Liked' : 'Disliked'} successfully`
                    : `${voteType === 'like' ? 'Like' : 'Dislike'} removed`;
                Toast.success(message);
                // Reload entries to reflect updated vote counts
                await loadEntries();
            } else {
                Toast.error(data.error || 'Failed to vote');
                button.disabled = false;
            }
        } catch (error) {
            Toast.error('Error voting. Please try again.');
            button.disabled = false;
        }
    }
    
    // Attach event listeners to comment vote buttons
    function attachCommentVoteListeners(container) {
        const voteButtons = container.querySelectorAll('.comment-actions .vote-button');
        voteButtons.forEach(button => {
            // Click handler
            button.addEventListener('click', async (e) => {
                e.stopPropagation();
                const commentId = button.getAttribute('data-comment-id');
                const voteType = button.getAttribute('data-vote');
                await handleCommentVote(commentId, voteType, button);
            });
            
            // Keyboard handler for accessibility
            button.addEventListener('keydown', async (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    e.stopPropagation();
                    const commentId = button.getAttribute('data-comment-id');
                    const voteType = button.getAttribute('data-vote');
                    await handleCommentVote(commentId, voteType, button);
                }
            });
        });
    }
    
    // Handle vote (like/dislike) on a comment
    async function handleCommentVote(commentId, voteType, button) {
        try {
            button.disabled = true;
            
            const formData = new FormData();
            formData.append('vote_type', voteType);
            
            const response = await fetch(`/api/comments/${encodeURIComponent(commentId)}/vote`, {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Determine the action and show appropriate message
                let message;
                if (data.user_vote === null) {
                    // Vote was removed
                    message = `${voteType === 'like' ? 'Like' : 'Dislike'} removed from comment`;
                } else if (data.user_vote === voteType) {
                    // Vote was added
                    message = `${voteType === 'like' ? 'Liked' : 'Disliked'} comment successfully`;
                } else {
                    // Vote was changed
                    message = `Changed to ${data.user_vote === 'like' ? 'like' : 'dislike'}`;
                }
                Toast.success(message);
                
                // Update the vote counts in the DOM using specific class names
                const commentItem = button.closest('.comment-item');
                const likeCount = commentItem.querySelector('.like-count');
                const dislikeCount = commentItem.querySelector('.dislike-count');
                
                if (likeCount) {
                    likeCount.textContent = data.vote_stats.likes;
                }
                if (dislikeCount) {
                    dislikeCount.textContent = data.vote_stats.dislikes;
                }
                
                button.disabled = false;
            } else {
                Toast.error(data.error || 'Failed to vote on comment');
                button.disabled = false;
            }
        } catch (error) {
            Toast.error('Error voting on comment. Please try again.');
            button.disabled = false;
        }
    }
    
    // Show comments modal for an entry
    async function showComments(entry) {
        // Create modal
        const modal = document.createElement('div');
        modal.className = 'comments-modal-overlay';
        modal.innerHTML = `
            <div class="comments-modal">
                <div class="comments-modal-header">
                    <h3>💬 Comments - ${entry.name.replace(/_/g, ' ')}</h3>
                    <button class="modal-close" onclick="this.closest('.comments-modal-overlay').remove()">✕</button>
                </div>
                <div class="comments-modal-body">
                    <div class="comments-list" id="comments-list-${entry._key}">
                        <div class="loading-comments">Loading comments...</div>
                    </div>
                    
                    <div class="comment-form">
                        <h4>Add a comment</h4>
                        <textarea id="comment-text-${entry._key}" placeholder="Write your comment here..." maxlength="5000"></textarea>
                        <div class="form-actions">
                            <button type="button" class="btn-cancel" onclick="this.closest('.comments-modal-overlay').remove()">
                                Cancel
                            </button>
                            <button type="button" class="btn-submit-comment" data-entry-id="${entry._key}">
                                Post Comment
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Load comments
        await loadComments(entry._key);
        
        // Handle comment submission
        const submitBtn = modal.querySelector('.btn-submit-comment');
        submitBtn.addEventListener('click', async () => {
            const textarea = document.getElementById(`comment-text-${entry._key}`);
            const text = textarea.value.trim();
            
            if (!text) {
                Toast.error('Please enter a comment');
                return;
            }
            
            submitBtn.disabled = true;
            submitBtn.textContent = 'Posting...';
            
            try {
                const formData = new FormData();
                formData.append('text', text);
                
                const response = await fetch(`/api/entries/${encodeURIComponent(entry._key)}/comments`, {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.success) {
                    Toast.success('Comment posted successfully');
                    textarea.value = '';
                    // Reload comments
                    await loadComments(entry._key);
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Post Comment';
                } else {
                    Toast.error(data.error || 'Failed to post comment');
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Post Comment';
                }
            } catch (error) {
                Toast.error('Error posting comment. Please try again.');
                submitBtn.disabled = false;
                submitBtn.textContent = 'Post Comment';
            }
        });
    }
    
    // Load comments for an entry
    async function loadComments(entryId) {
        try {
            const response = await fetch(`/api/entries/${encodeURIComponent(entryId)}/comments`);
            const data = await response.json();
            
            const commentsList = document.getElementById(`comments-list-${entryId}`);
            
            if (data.success && data.comments && data.comments.length > 0) {
                // Organize comments by parent-child relationship
                const topLevelComments = data.comments.filter(c => !c.parent_comment_id);
                const replies = data.comments.filter(c => c.parent_comment_id);
                
                let html = '';
                topLevelComments.forEach(comment => {
                    html += renderComment(comment);
                    
                    // Add replies
                    const commentReplies = replies.filter(r => r.parent_comment_id === comment.id);
                    if (commentReplies.length > 0) {
                        html += '<div class="comment-replies">';
                        commentReplies.forEach(reply => {
                            html += renderComment(reply);
                        });
                        html += '</div>';
                    }
                });
                
                commentsList.innerHTML = html;
                
                // Attach vote button event listeners
                attachCommentVoteListeners(commentsList);
            } else {
                commentsList.innerHTML = '<div class="no-comments">No comments yet. Be the first to comment!</div>';
            }
        } catch (error) {
            console.error('Error loading comments:', error);
            const commentsList = document.getElementById(`comments-list-${entryId}`);
            if (commentsList) {
                commentsList.innerHTML = '<div class="error-comments">Failed to load comments</div>';
            }
        }
    }
    
    // Render a single comment
    function renderComment(comment) {
        const date = formatDate(comment.created_at);
        
        // Determine user role and styling
        let roleClass = '';
        let roleBadge = '';
        
        if (comment.user_is_admin) {
            roleClass = 'comment-author-admin';
            roleBadge = '<span class="user-badge badge-admin">👑 ADMIN</span>';
        } else if (comment.user_is_moderator) {
            roleClass = 'comment-author-mod';
            roleBadge = '<span class="user-badge badge-mod">🛡️ MOD</span>';
        } else if (comment.user_is_uploader) {
            roleClass = 'comment-author-uploader';
            roleBadge = '<span class="user-badge badge-uploader">⬆️ UPLOADER</span>';
        } else {
            roleClass = 'comment-author-downloader';
            roleBadge = '<span class="user-badge badge-downloader">⬇️ DOWNLOADER</span>';
        }
        
        // Vote counts
        const likesCount = comment.likes_count || 0;
        const dislikesCount = comment.dislikes_count || 0;
        
        return `
            <div class="comment-item" data-comment-id="${comment.id}">
                <div class="comment-header">
                    <span class="comment-author ${roleClass}">${escapeHtml(comment.username)}</span>
                    ${roleBadge}
                    <span class="comment-date">${date}</span>
                </div>
                <div class="comment-text">${escapeHtml(comment.text)}</div>
                <div class="comment-actions">
                    <span class="vote-button" data-vote="like" data-comment-id="${comment.id}" 
                          role="button" tabindex="0" aria-label="Like this comment" title="Like this comment">👍</span>
                    <span class="vote-count like-count">${likesCount}</span>
                    <span class="vote-button" data-vote="dislike" data-comment-id="${comment.id}" 
                          role="button" tabindex="0" aria-label="Dislike this comment" title="Dislike this comment">👎</span>
                    <span class="vote-count dislike-count">${dislikesCount}</span>
                </div>
            </div>
        `;
    }
    
    // Escape HTML to prevent XSS
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // Format file size
    function formatSize(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    // Format date
    function formatDate(dateString) {
        if (!dateString) return 'Unknown';
        
        try {
            const date = new Date(dateString);
            const now = new Date();
            
            // Reset time components for accurate day comparison
            const dateOnly = new Date(date.getFullYear(), date.getMonth(), date.getDate());
            const nowOnly = new Date(now.getFullYear(), now.getMonth(), now.getDate());
            const diffTime = nowOnly - dateOnly;
            const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
            
            if (diffDays === 0) return 'Today';
            if (diffDays === 1) return 'Yesterday';
            if (diffDays < 7) return `${diffDays} days ago`;
            if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
            if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`;
            
            return date.toLocaleDateString();
        } catch (error) {
            return dateString;
        }
    }
    
    // Show loading state
    function showLoading() {
        if (loadingState) {
            loadingState.classList.remove('hidden');
        }
        if (resultsGrid) {
            resultsGrid.classList.add('hidden');
        }
        hideEmptyState();
    }
    
    // Hide loading state
    function hideLoading() {
        if (loadingState) {
            loadingState.classList.add('hidden');
        }
        if (resultsGrid) {
            resultsGrid.classList.remove('hidden');
        }
    }
    
    // Show empty state
    function showEmptyState() {
        if (emptyState) {
            emptyState.classList.remove('hidden');
        }
    }
    
    // Hide empty state
    function hideEmptyState() {
        if (emptyState) {
            emptyState.classList.add('hidden');
        }
    }
    
    // Show error message
    function showError(message) {
        if (resultsGrid) {
            resultsGrid.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">⚠️</div>
                    <div class="empty-state-title">Error</div>
                    <div class="empty-state-message">${message}</div>
                </div>
            `;
            resultsGrid.classList.remove('hidden');
        }
    }
    
    // Helper function to validate if a hash is valid (not empty, null, or 'processing')
    function isHashValid(hash) {
        return hash && hash !== 'processing' && hash.length > 0;
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
