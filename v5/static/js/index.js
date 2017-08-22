var server = location.protocol + '//' + location.hostname + (location.port ? ':' + location.port : '');

var arduino_check_connect_sec = 60 * 5;
var arduino_check_broken_connect_sec = 60;

var branch_names = [];

$(document).ready(function() {

    // var $loading = $('#loader').hide();
    // $(document)
    //     .ajaxStart(function() {
    //         $loading.show();
    //     })
    //     .ajaxStop(function() {
    //         $loading.hide();
    //     });

    //Rename branches
    $.ajax({
        url: server + '/branches_names',
        success: function(data) {
            list = data['list']
            for (j in list) {
                item = list[j]
                branch_names[item['id']] = item['name']
            }

            for (var i = 1; i < branch_names.length; i++) {
                if (branch_names[i] != undefined) {
                    $('#card-' + i).show();
                    $('#title-' + i).text(branch_names[i]);
                } else {
                    $('#card-' + i).hide();
                }
            }
        }
    });


   $('#irrigation_intervals').on('input', function(e) {
        console.log("here");
        var selected = $(this).val()
        if (selected <= 1 || selected == undefined) {
            $('#irrigation_time_wait_group').hide();
        } else {
            $('#irrigation_time_wait_group').show();
        }
    });

    var socket = io.connect(server, {
        'sync disconnect on unload': true
    });
    socket.on('connect', function() {
        console.log("connected to websocket");
    });

    socket.on('branch_status', function(msg) {
        console.log('Message received. New brach status: ' + msg.data);
        update_branches(msg.data);
    });

    // //Add arduino touch script to determine if connection is alive
    // (function update_weather() {
    //     $.ajax({
    //         url: server + '/weather',
    //         success: function(data) {
    //             $("#temp_header").text("Температура воздуха: " + data['temperature'] + " C*");
    //             setTimeout(update_weather, 60 * 1000 * 30);
    //         },
    //         global: false
    //     });
    // })();


    // touch_analog_sensor();

    // //Add arduino touch script to determine if connection is alive
    // (function worker() {
    //     $.ajax({
    //         url: server + '/arduino_status',
    //         beforeSend: function(xhr, opts) {
    //             set_status_spinner();

    //             if ($('#time_modal').hasClass('in')) {
    //                 xhr.abort();
    //             }
    //         },
    //         success: function(data) {
    //             $('#loader').hide();
    //             console.log("connected to arduino");

    //             set_status_ok();

    //             update_branches(data);
    //             setTimeout(worker, arduino_check_connect_sec * 1000);
    //         },
    //         error: function() {
    //             console.error("Can't connect to arduino");

    //             set_status_error();

    //             $('#loader').show()
    //             setTimeout(worker, arduino_check_broken_connect_sec * 1000);
    //         },
    //         complete: function() {
    //             $("#button_gif").removeClass("fa-spin");
    //         }
    //     });
    // })();

    $('#irrigate_modal').on('hidden.bs.modal', function() {
        $('#irrigation_minutes').val("");
        $('#irrigation_intervals').val(1);
        $('#irrigation_time_wait').val(1);

        $('#irrigation_time_wait_group').hide();

        update_branches_request();
    })

    $(".btn-open-modal").click(function() {
        index = $(this).data('id');
        name = branch_names[index];

        $('#irrigate_modal').data('id', index);
        $('.modal-title').html(name);
        $('#irrigate_modal').modal('show');
    });

    //Function to start irrigation
    $(".start-irrigation").click(function() {
        index = $('#irrigate_modal').data('id');
        time = $("#irrigation_minutes").val();
        interval_quantity = $("#irrigation_intervals").val();
        time_wait = $("#irrigation_time_wait").val();
        console.log(branch_names[index] + " will be activated on " + time + " minutes, " + interval_quantity + " times with " + time_wait + " period");
        branch_on(index, time, interval_quantity, time_wait);
    });

});

function branch_on(index, time_minutes, interval_quantity, time_wait) {
    if (interval_quantity == 1) {
        mode = 'single'
    } else {
        mode = 'interval'
    }

    $.ajax({
        url: server + '/activate_branch',
        type: "get",
        data: {
            'mode': mode,
            'id': index,
            'time_min': time_minutes,
            'quantity': interval_quantity,
            'time_wait': time_wait
        },
        success: function(data) {
            console.log('Line ' + branch_names[index] + ' should be active now');
            update_branches(data);
        },
        error: function() {
            alert("Не могу включить " + branch_names[index]);
            console.error("Can't update " + branch_names[index]);
            toogle_checkbox(index, 0);

            set_status_error();
        }
    });
}

function branch_off(index) {
    $.ajax({
        url: server + '/deactivate_branch',
        type: "get",
        data: {
            'id': index,
            'mode': 'manually'
        },
        success: function(data) {
            console.log('Line ' + branch_names[index] + ' should be deactivated now');
            update_branches(data);
        },
        error: function() {
            alert("Не могу выключить " + branch_names[index]);
            console.error("Can't update " + branch_names[index]);
            toogle_checkbox(index, 1);
            set_status_error();
        }
    });
}

function update_branches_request() {
    $.ajax({
        url: server + '/arduino_status',
        success: function(data) {
            update_branches(data);
        },
        error: function() {
            console.error("Branches statuses are out-of-date");
            set_status_error();
        }
    });
}

function update_branches(json) {
    branches = JSON.parse(json);
    for (var i = 0; i >= 16; i++) {
        toogle_card(i, branches['\'' + i + '\'']);
    }
    toogle_card(17, branches['pump']);
}

function toogle_card(element_id, branch_state) {
    if (branch_state == 1) {
        $('#card-' + element_id).addClass("card-irrigate-active");
        $('#btn-' + element_id).removeClass("btn-open-modal");
        if (element_id != 17)
            $('#btn-' + element_id).html('Остановить полив');
        else
            $('#btn-' + element_id).html('Выключить');
    } else {
        $('#card-' + element_id).removeClass("card-irrigate-active");
        $('#btn-' + element_id).addClass("btn-open-modal");
        if (element_id != 17)
            $('#btn-' + element_id).html('Полить');
        else
            $('#btn-' + element_id).html('Включить');
    }
}

function touch_arduino() {
    $.ajax({
        url: server + '/arduino_status',
        beforeSend: function(xhr, opts) {
            $("#arduino_status").text(class_spin.msg);
            $("#button_gif").removeClass().addClass(class_spin.class);
        },
        success: function(data) {
            console.log("connected to arduino");
            set_status_ok();
            update_branches(data);
        },
        error: function() {
            //$('button').setClass('btn btn-primary');
            console.error("Can't connect to arduino");
            set_status_error();
        }
    });
}

function touch_analog_sensor() {
    $.ajax({
        url: server + '/humidity_sensor',
        success: function(data) {
            $("#humidity_text").text(data['text']);
        }
    });
}

// this is for status button
var class_ok = {
    msg: ' Система активна',
    class: 'fa fa-refresh'
}
var class_spin = {
    msg: ' Проверка статуса системы...',
    class: 'fa fa-refresh fa-spin'
}
var class_err = {
    msg: ' Ошибка! Нажмите, чтобы обновить статус',
    class: 'fa fa-exclamation-circle'
}

function set_status_error() {
    $("#arduino_status").text(class_err.msg);
    $("#button_gif").removeClass().addClass(class_err.class);
    $("#status_button").removeClass().addClass('btn btn-danger btn-md');
}

function set_status_ok() {
    $("#arduino_status").text(class_ok.msg);
    $("#button_gif").removeClass().addClass(class_ok.class);
    $("#status_button").removeClass().addClass('btn btn-default btn-md');

}

function set_status_spinner() {
    $("#arduino_status").text(class_spin.msg);
    $("#button_gif").removeClass().addClass(class_spin.class);
    $("#status_button").removeClass().addClass('btn btn-default btn-md');
}