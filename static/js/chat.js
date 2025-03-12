document.addEventListener('DOMContentLoaded', function() {
    // DOM elements
    const chatContainer = document.getElementById('chat-container');
    const messageForm = document.getElementById('message-form');
    const messageInput = document.getElementById('message-input');
    const resetBtn = document.getElementById('reset-btn');
    const entityPanel = document.getElementById('entity-panel');
    const entityDisplay = document.getElementById('entity-display');
    
    // Add welcome message
    addBotMessage("Hello! I'm your scheduling assistant. How can I help you today?");
    
    // Listen for form submission
    messageForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const message = messageInput.value.trim();
        if (!message) return;
        
        // Add user message to chat
        addUserMessage(message);
        
        // Clear input
        messageInput.value = '';
        
        // Show typing indicator
        const typingIndicator = document.createElement('div');
        typingIndicator.className = 'flex items-start mb-4 fade-in';
        typingIndicator.innerHTML = `
            <div class="w-10 h-10 rounded-full bg-blue-500 flex items-center justify-center text-white mr-3">
                <i class="fas fa-robot"></i>
            </div>
            <div class="bg-blue-100 rounded-lg py-2 px-4 max-w-md">
                <span class="typing-indicator font-medium">Thinking</span>
            </div>
        `;
        typingIndicator.id = 'typing-indicator';
        chatContainer.appendChild(typingIndicator);
        chatContainer.scrollTop = chatContainer.scrollHeight;
        
        // Send message to server
        sendMessage(message);
    });
    
    // Reset button
    resetBtn.addEventListener('click', function() {
        // Confirm before resetting
        if (confirm('Are you sure you want to reset this conversation?')) {
            fetch('/reset', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                // Clear chat
                chatContainer.innerHTML = '';
                
                // Add welcome message with bot response
                addBotMessage(data.response);
                
                // Hide entity panel
                entityPanel.classList.add('hidden');
            })
            .catch(error => {
                console.error('Error resetting chat:', error);
                addBotMessage("Sorry, there was an error resetting the chat. Please try again.");
            });
        }
    });
    
    // Function to send message to server
    function sendMessage(message) {
        fetch('/message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message })
        })
        .then(response => response.json())
        .then(data => {
            // Remove typing indicator
            const typingIndicator = document.getElementById('typing-indicator');
            if (typingIndicator) {
                typingIndicator.remove();
            }
            
            // Add bot response
            addBotMessage(data.response);
            
            // Update entity panel if there are entities
            updateEntityPanel(data.entities, data.complete);
        })
        .catch(error => {
            console.error('Error sending message:', error);
            
            // Remove typing indicator
            const typingIndicator = document.getElementById('typing-indicator');
            if (typingIndicator) {
                typingIndicator.remove();
            }
            
            addBotMessage("Sorry, there was an error processing your message. Please try again.");
        });
    }
    
    // Function to add user message to chat
    function addUserMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.className = 'flex items-start mb-4 justify-end fade-in';
        messageElement.innerHTML = `
            <div class="bg-blue-600 text-white rounded-lg py-2 px-4 max-w-md">
                <p>${escapeHtml(message)}</p>
            </div>
            <div class="w-10 h-10 rounded-full bg-gray-300 flex items-center justify-center ml-3">
                <i class="fas fa-user"></i>
            </div>
        `;
        chatContainer.appendChild(messageElement);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
    
    // Function to add bot message to chat
    function addBotMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.className = 'flex items-start mb-4 fade-in';
        
        // Format the message content if it's an email selection
        const formattedMessage = formatEmailSelectionMessage(message);
        
        messageElement.innerHTML = `
            <div class="w-10 h-10 rounded-full bg-blue-500 flex items-center justify-center text-white mr-3">
                <i class="fas fa-robot"></i>
            </div>
            <div class="bg-blue-100 rounded-lg py-2 px-4 max-w-md">
                ${formattedMessage}
            </div>
        `;
        chatContainer.appendChild(messageElement);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
    
    // Function to update entity panel
    function updateEntityPanel(entities, isComplete) {
        if (!entities || Object.keys(entities).length === 0) {
            return;
        }
        
        // Show entity panel
        entityPanel.classList.remove('hidden');
        
        // Clear previous entities
        entityDisplay.innerHTML = '';
        
        const entityColors = {
            'DATE': 'bg-green-200 text-green-800',
            'TIME': 'bg-blue-200 text-blue-800',
            'DURATION': 'bg-purple-200 text-purple-800',
            'ATTENDEE': 'bg-yellow-200 text-yellow-800'
        };
        
        // Add entities to display
        Object.entries(entities).forEach(([type, values]) => {
            if (values && values.length > 0) {
                const entityElement = document.createElement('div');
                entityElement.className = 'mb-2';
                
                const typeLabel = document.createElement('div');
                typeLabel.className = 'text-xs font-semibold text-gray-600 mb-1';
                typeLabel.textContent = type;
                
                const valueContainer = document.createElement('div');
                valueContainer.className = 'flex flex-wrap';
                
                values.forEach(value => {
                    // Check if value contains email (in parentheses)
                    let displayValue = value;
                    let emailValue = '';
                    
                    const emailMatch = value.match(/(.+)\s+\((.+@.+\..+)\)/);
                    if (emailMatch) {
                        displayValue = emailMatch[1];
                        emailValue = emailMatch[2];
                    }
                    
                    const valueTag = document.createElement('span');
                    
                    if (emailValue) {
                        // If this is an attendee with email, use email chip style
                        valueTag.className = 'email-chip';
                        valueTag.innerHTML = `
                            <span class="email-chip-name">${escapeHtml(displayValue)}</span>
                            <span class="email-chip-email">${escapeHtml(emailValue)}</span>
                        `;
                    } else {
                        // Regular entity tag
                        valueTag.className = `entity-tag ${entityColors[type] || 'bg-gray-200 text-gray-800'}`;
                        valueTag.textContent = value;
                    }
                    
                    valueContainer.appendChild(valueTag);
                });
                
                entityElement.appendChild(typeLabel);
                entityElement.appendChild(valueContainer);
                entityDisplay.appendChild(entityElement);
            }
        });
        
        // If context is complete, add a checkmark
        if (isComplete) {
            const completeElement = document.createElement('div');
            completeElement.className = 'col-span-2 mt-2 text-center py-1 bg-green-100 text-green-800 rounded-md';
            completeElement.innerHTML = '<i class="fas fa-check-circle mr-1"></i> All required information collected';
            entityDisplay.appendChild(completeElement);
        }
    }
    
    // This parses the message to check for and format email selection options
    function formatEmailSelectionMessage(message) {
        // Check if this is an email selection message
        if (message.includes('Multiple contacts found for') && message.includes('Please select one or more by number')) {
            // Split the message into parts
            const [introText, optionsText] = message.split('Please select one or more by number');
            
            // Format the introduction part
            const formattedIntro = `<p class="mb-2">${introText} Please select one or more by number (e.g., "1", "2", "1 and 2", or "all"):</p>`;
            
            // Format each option as a clickable button with checkboxes
            const options = optionsText.trim().split('\n');
            let formattedOptions = '<div class="grid gap-2 mt-2">';
            
            options.forEach(option => {
                const [number, details] = option.split('. ', 2);
                formattedOptions += `
                    <button class="email-option text-left bg-blue-50 hover:bg-blue-100 py-2 px-3 rounded-md transition-colors" 
                            data-number="${number}">
                        <label class="flex items-center cursor-pointer">
                            <input type="checkbox" class="mr-2 h-4 w-4 text-blue-600 focus:ring-blue-500 rounded">
                            <span class="font-semibold text-blue-600">${number}.</span> ${details}
                        </label>
                    </button>
                `;
            });
            
            // Add select all option and confirm button
            formattedOptions += `
                <div class="mt-2 flex justify-between">
                    <button id="select-all" class="text-blue-600 text-sm hover:text-blue-800">
                        Select All
                    </button>
                    <button id="submit-selection" class="bg-blue-600 text-white text-sm py-1 px-3 rounded hover:bg-blue-700">
                        Confirm Selection
                    </button>
                </div>
            `;
            
            formattedOptions += '</div>';
            
            // Return formatted HTML
            return formattedIntro + formattedOptions;
        }
        
        // If this message has emails in it, format them nicely
        if (message.includes('@') && message.includes('(') && message.includes(')')) {
            // Replace email mentions with formatted HTML
            return message.replace(/([A-Za-z\s]+)\s+\(([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\)/g, 
                '<span class="text-blue-700 font-medium">$1</span> <span class="text-blue-500 text-sm">($2)</span>');
        }
        
        // Not an email-related message, return as is
        return escapeHtml(message);
    }
    
    // Function to handle clicks on email options
    function setupEmailOptionListeners() {
        // Store selected options
        let selectedOptions = new Set();
        
        // Use event delegation for dynamically added elements
        document.addEventListener('click', function(e) {
            // Handle checkbox clicks in email options
            if (e.target && e.target.type === 'checkbox' && e.target.closest('.email-option')) {
                const option = e.target.closest('.email-option');
                const number = option.getAttribute('data-number');
                
                if (e.target.checked) {
                    selectedOptions.add(number);
                } else {
                    selectedOptions.delete(number);
                }
                
                // Don't submit yet, wait for the confirm button
                e.preventDefault();
                return;
            }
            
            // Handle the select all button
            if (e.target && e.target.id === 'select-all') {
                const checkboxes = document.querySelectorAll('.email-option input[type="checkbox"]');
                const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                
                checkboxes.forEach(checkbox => {
                    checkbox.checked = !allChecked;
                    const number = checkbox.closest('.email-option').getAttribute('data-number');
                    
                    if (!allChecked) {
                        selectedOptions.add(number);
                    } else {
                        selectedOptions.delete(number);
                    }
                });
                
                e.preventDefault();
                return;
            }
            
            // Handle the confirm selection button
            if (e.target && e.target.id === 'submit-selection') {
                if (selectedOptions.size === 0) {
                    // Alert user to select at least one option
                    alert('Please select at least one contact.');
                    return;
                }
                
                // Format selection for message
                const selectionText = Array.from(selectedOptions).join(' and ');
                
                // Add user message showing the selection
                addUserMessage(selectionText);
                
                // Send the selection to the server
                sendMessage(selectionText);
                
                // Clear selections
                selectedOptions.clear();
                
                e.preventDefault();
                return;
            }
            
            // Handle direct click on email option (for backwards compatibility)
            const target = e.target.closest('.email-option');
            if (target && !e.target.closest('input[type="checkbox"]')) {
                const checkbox = target.querySelector('input[type="checkbox"]');
                if (checkbox) {
                    // Toggle checkbox
                    checkbox.checked = !checkbox.checked;
                    
                    const number = target.getAttribute('data-number');
                    
                    if (checkbox.checked) {
                        selectedOptions.add(number);
                    } else {
                        selectedOptions.delete(number);
                    }
                }
            }
        });
    }
    
    // Escape HTML to prevent XSS
    function escapeHtml(html) {
        if (typeof html !== 'string') return '';
        
        const div = document.createElement('div');
        div.textContent = html;
        return div.innerHTML;
    }
    
    // Set up email option listeners
    setupEmailOptionListeners();
});