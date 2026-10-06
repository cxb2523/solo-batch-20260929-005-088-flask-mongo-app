$(document).ready(function() {
    console.log("Ready!");


    // Manage edit-name-button text
    $('#edit-name').on('hide.bs.collapse', function() {
        $('a.edit-name-button').html("Edit");
    });
    $('#edit-name').on('show.bs.collapse', function() {
        $('a.edit-name-button').html("Close");
    });


    // Validate password
    $("#submit-button").click(function(event) {
        var pass = $("#pass").val();
        var confirmation = $("#confirmation").val();
        var regex = /^(?=.*[0-9])(?=.*[!@#$%^&*])[a-zA-Z0-9!@#$%^&*]{8,32}$/;
        if (!pass.match(regex)) {
            event.preventDefault();
            alert("Password must be 8-32 characters long and contain at least one number and one special character.");
        } else if (pass != confirmation) {
            event.preventDefault();
            alert("Password and confirmation do not match. Please re-enter them and try again.");
        }
    });


    // Resend validation email
    $("a.verify-button").click(function(event) {
        event.preventDefault();
        $(this).html("Sending email");
        $(this).css('pointer-events', 'none');
        $(this).addClass("text-muted");
        $.post("/verify", $("form.verify-form").serialize())
            .done(function(response) {
                console.log(response);
                $("a.verify-button").html("Email sent");
            })
            .fail(function(response) {
                console.log(response)
            });
    });


    // Add note
    $("button.add-note-button").click(function() {
        $.post("/add_note", $("form.add-note-form").serialize())
            .done(function(response) {
                console.log(response);
                location.reload(true);
            })
            .fail(function(response) {
                console.log(response)
            });
    });


    // Delete note
    $("button.delete-note-button").click(function() {
        $.post("/delete_note", $("form.delete-note-form").serialize())
            .done(function(response) {
                console.log(response);
                location.reload(true);
            })
            .fail(function(response) {
                console.log(response)
            });
    });


    // Send message
    $("button.send-message-button").click(function() {
        $.post("/send_message", $("form.send-message-form").serialize())
            .done(function(response) {
                console.log(response);
                location.reload(true);
            })
            .fail(function(response) {
                console.log(response)
            });
    });


    // Delete message
    $("button.delete-message-button").click(function() {
        $.post("/delete_message", $("form.delete-message-form").serialize())
            .done(function(response) {
                console.log(response);
                location.reload(true);
            })
            .fail(function(response) {
                console.log(response)
            });
    });


    // Hide sent message
    $("button.hide-sent-message-button").click(function() {
        $.post("/hide_sent_message", $("form.hide-sent-message-form").serialize())
            .done(function(response) {
                console.log(response);
                location.reload(true);
            })
            .fail(function(response) {
                console.log(response)
            });
    });


    // Change Name
    $("button.change-name-button").click(function() {
        $.post("/change_name", $("form.change-name-form").serialize())
            .done(function(response) {
                console.log(response);
                location.reload(true);
            })
            .fail(function(response) {
                console.log(response)
            });
    });


    // Delete account
    $("button.second-delete").click(function(event) {
        if (confirm("Are you sure you want to delete your account?")) {
            console.log("Deleting account");
            $.post("/delete_account", $("form.delete-account-form").serialize())
                .done(function(response) {
                    console.log(response);
                    location.href = "/";
                })
                .fail(function(response) {
                    console.log(response)
                });
        } else {
            event.preventDefault();
            $("div.delete-account").collapse("hide");
        }
    });


    // Toggle delete button
    $("div.delete-account").on('hide.bs.collapse', function() {
        $("div.account-card").removeClass("border-danger");
        $("div.account-card").addClass("border-secondary");
        $("p.delete-warning").removeClass("text-danger");
        $("button.first-delete").html("Delete account");
    });
    $("div.delete-account").on('show.bs.collapse', function() {
        $("div.account-card").removeClass("border-secondary");
        $("div.account-card").addClass("border-danger");
        $("p.delete-warning").addClass("text-danger");
        $("button.first-delete").html("Hide the red button!");
    });


    // Notes page: debounced filter + stale-response guard
    if ($("#notes-filter-form").length) {
        var notesState = {
            page: 1,
            debounceTimer: null,
            // Monotonic request sequence: only the latest request may render,
            // so a slow earlier response can never overwrite newer results.
            requestSeq: 0
        };

        function notesParams() {
            var params = { format: "json", page: notesState.page, per_page: $("#notes-per-page").val() };
            var q = $("#notes-q").val().trim();
            if (q) {
                params.q = q;
            }
            // Tags are intersected server-side: send one repeated param per tag
            var tags = $("#notes-tags").val().split(",")
                .map(function(t) { return t.trim(); })
                .filter(function(t) { return t.length > 0; });
            if (tags.length) {
                params.tag = tags;
            }
            return params;
        }

        function renderNotes(data) {
            var $results = $("#notes-results").empty();
            if (!data.notes.length) {
                $results.append($("<p>").text("No notes match your filters."));
            }
            data.notes.forEach(function(note) {
                var $card = $("<div>", { "class": "card border border-muted bg-light rounded mb-3" });
                var $body = $("<div>", { "class": "card-body" });
                $body.append($("<h3>", { "class": "card-title" }).text(note.title));
                $body.append($("<p>", { "class": "card-text" }).text(note.body));
                if (note.tags && note.tags.length) {
                    $body.append($("<p>", { "class": "card-text text-muted" })
                        .text("Tags: " + note.tags.join(", ")));
                }
                $card.append($body);
                $card.append($("<div>", { "class": "card-footer bg-light" })
                    .append($("<p>", { "class": "my-auto text-muted" }).text(note.date_string || "")));
                $results.append($card);
            });
            $("#notes-summary").text(data.total + " note(s) match the current filters.");
            $("#notes-page-info").text("Page " + data.page + " of " + data.pages);
            $("#notes-prev-item").toggleClass("disabled", data.page <= 1);
            $("#notes-next-item").toggleClass("disabled", data.page >= data.pages);
        }

        function fetchNotes() {
            notesState.requestSeq += 1;
            var seq = notesState.requestSeq;
            $.getJSON("/notes", notesParams())
                .done(function(data) {
                    if (seq !== notesState.requestSeq) {
                        // Stale response: a newer request is in flight or done
                        return;
                    }
                    notesState.page = data.page;
                    renderNotes(data);
                })
                .fail(function(response) {
                    if (seq !== notesState.requestSeq) {
                        return;
                    }
                    console.log(response);
                });
        }

        function scheduleFetch(resetPage) {
            if (resetPage) {
                notesState.page = 1;
            }
            clearTimeout(notesState.debounceTimer);
            notesState.debounceTimer = setTimeout(fetchNotes, 300);
        }

        $("#notes-q, #notes-tags").on("input", function() { scheduleFetch(true); });
        $("#notes-per-page").on("change", function() { scheduleFetch(true); });
        $("#notes-prev").click(function() {
            if (notesState.page > 1) {
                notesState.page -= 1;
                fetchNotes();
            }
        });
        $("#notes-next").click(function() {
            notesState.page += 1;
            fetchNotes();
        });

        fetchNotes();
    }

});
