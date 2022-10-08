odoo.define('businesssuite_ecommerce_rental.website_sale_rental', function (require) {
    "use strict";
    var ajax = require('web.ajax');
    var publicWidget = require('web.public.widget');
    var website_sale = require('website_sale.website_sale');
    const wUtils = require('website.utils');

    $(document).ready(function () {

        var is_rental_product = false
        var input_rental_product = $('.oe_website_sale').find('input[type="hidden"][name="is_rental_product"]').val();
        var rental_renew_modal = $('#RentalRenewModal').find('input[type="hidden"][name="is_rental_product"]').val()

        if (input_rental_product == "True") {
            is_rental_product = true
        } else {
            is_rental_product = false
        }

        publicWidget.registry.WebsiteSale.include({
            _submitForm: function () {
                if (input_rental_product == 'True') {
                    var form_keys = this.$form.serializeArray();
                    $.each(form_keys, (i, v) => {
                        if (!_.has(this.rootProduct, v.name)) this.rootProduct[v.name] = v.value;
                    });
                }
                this._super.apply(this, arguments);
            },
        });

        function disable_add_to_cart() {
            $('#add_to_cart').attr("disabled", "1");
            $('#add_to_cart').addClass("disabled");
            $('#add_to_cart').removeAttr("href");
        }

        function enable_add_to_cart() {
            $('#add_to_cart').removeAttr("disabled");
            $('#add_to_cart').removeClass("disabled");
            $('#add_to_cart').attr("href", "#");
        }

        if (is_rental_product) {
            if (!document.getElementById("custom") && !document.getElementById("standard")) {
                disable_add_to_cart()
            }
            if (document.getElementById("custom") && document.getElementById("custom").checked != true) {
                disable_add_to_cart()
            }
        }

        $('[data-toggle="popover"]').popover();

        $('tr.rental_order_row').click(function () {
            var href = $(this).find("a").attr("href");
            if (href) {
                window.location = href;
            }
        });

        $('#standard_tab_li').on('click', function (event) {
            if (is_rental_product) {
                if (document.getElementById("custom")) {
                    document.getElementById("custom").checked = false;
                }
                if (document.getElementById("standard")) {
                    document.getElementById("standard").checked = true;
                }

                var $form = $(this).closest('form');
                var product_id = parseInt($form.find('input[type="hidden"][name="product_id"]').first().val());
                var radios = document.getElementsByName('tenure_id');
                var tenure_id;
                for (var i = 0, length = radios.length; i < length; i++) {
                    if (radios[i].checked) {
                        tenure_id = radios[i].value
                        break;
                    }
                }
                enable_add_to_cart()
                // if(event.isDefaultPrevented()){
                //     $form.submit();
                // }
                if (!isNaN(tenure_id)) {
                    $('.rental_loader').show();
                    ajax.jsonRpc("/get/tenure/price", 'call', {
                        'tenure_id': tenure_id,
                        'product_id': product_id,
                    }).then(function (data) {
                        $("#check_tenure_price").html(data)
                        $('.rental_loader').hide();
                    })
                    // $('#add_to_cart').removeAttr("disabled");
                    // if(event.isDefaultPrevented()){
                    //     $form.submit();
                    // }
                }
            }
        });

        $('#custom_tab_li').on('click', function (event) {
            if (is_rental_product) {
                document.getElementById("custom").checked = true;
                document.getElementById("standard").checked = false;

                var $form = $(this).closest('form');
                var tenure_uom_id = parseInt($("select#tenure_uom option:selected").val())
                var tenure_value_div = $('#tenure_value')
                var tenure_value = tenure_value_div.val()
                var product_id = parseInt($form.find('input[type="hidden"][name="product_id"]').first().val());
                if (tenure_value === '') {
                    tenure_value_div.addClass("invalid");
                    $('div.error_content').html("Please enter a valid value")
                    disable_add_to_cart()
                }
                if (!isNaN(tenure_uom_id) && tenure_value != '' && document.getElementById("custom").checked == true) {
                    $('.rental_loader').show();
                    ajax.jsonRpc("/get/tenure/price", 'call', {
                        'tenure_uom_id': tenure_uom_id,
                        'tenure_value': tenure_value,
                        'product_id': product_id,
                    }).then(function (data) {
                        if (tenure_value <= 0) {
                            tenure_value_div.addClass("invalid");
                            $('div.error_content').html("Value must be greater than 0.")
                            disable_add_to_cart()
                        }
                            // else if(data.error == "true"){
                            //     tenure_value_div.addClass("invalid");
                            //     $('div.error_content').html("Value must be less than or equal to " + data.max_value + ".")
                            //     $('#add_to_cart').attr("disabled","1");
                        // }
                        else if (data.error == "false") {
                            if (tenure_value_div.hasClass("invalid")) {
                                tenure_value_div.removeClass("invalid");
                                $('div.error_content').html("")
                            }
                            $("#check_tenure_price").html(data.tenure_price)
                            $('#custom_tenure_price').val(data.tenure_price)
                            enable_add_to_cart()
                            // if(event.isDefaultPrevented()){
                            //     $form.submit();
                            // }
                        }
                        $('.rental_loader').hide();
                    });
                }
            }
        });

        $(".tenure_radio").on('click', function () {
            if (is_rental_product || rental_renew_modal) {
                var $form = $(this).closest('form');
                var product_id = parseInt($form.find('input[type="hidden"][name="product_id"]').first().val());
                var radios = document.getElementsByName('tenure_id');
                var tenure_id;
                for (var i = 0, length = radios.length; i < length; i++) {
                    if (radios[i].checked) {
                        tenure_id = radios[i].value
                        break;
                    }
                }
                if (!isNaN(tenure_id)) {
                    $('.rental_loader').show();
                    ajax.jsonRpc("/get/tenure/price", 'call', {
                        'tenure_id': tenure_id,
                        'product_id': product_id,
                    }).then(function (data) {
                        $("#check_tenure_price").html(data)
                        $('.rental_loader').hide();
                    })
                }
            }
        })

        $('#tenure_uom').on('change', function () {
            if (is_rental_product) {
                var $form = $(this).closest('form');
                var tenure_uom_id = parseInt($("select#tenure_uom option:selected").val())
                var product_id = parseInt($form.find('input[type="hidden"][name="product_id"]').first().val());
                // document.getElementById("tenure_value").defaultValue = "1";
                $('#tenure_value').removeClass("invalid");
                $('div.error_content').html("")
                if (!isNaN(tenure_uom_id)) {
                    $('.rental_loader').show();
                    ajax.jsonRpc("/set/tenure/maxvalue", 'call', {
                        'tenure_uom_id': tenure_uom_id,
                        'product_id': product_id,
                    }).then(function (data) {
                        $('#tenure_value').attr('max', data.max_value);
                        $('.rental_loader').hide();
                    });
                }
            }
        })

        $('.oe_website_sale #add_to_cart')
            .off('click')
            .removeClass('a-submit')
            .click(_.debounce(function (event) {
                event.preventDefault();
                if (is_rental_product) {
                    event.preventDefault();
                    var $form = $(this).closest('form');
                    var tenure_uom_id = parseInt($("select#tenure_uom option:selected").val())
                    var tenure_value_div = $('#tenure_value')
                    var tenure_value = tenure_value_div.val()
                    var product_id = parseInt($form.find('input[type="hidden"][name="product_id"]').first().val());
                    if (!isNaN(tenure_uom_id) && tenure_value != '' && document.getElementById("custom").checked == true) {
                        $('.rental_loader').show();
                        ajax.jsonRpc("/get/tenure/price", 'call', {
                            'tenure_uom_id': tenure_uom_id,
                            'tenure_value': tenure_value,
                            'product_id': product_id,
                        }).then(function (data) {
                            if (tenure_value <= 0) {
                                tenure_value_div.addClass("invalid");
                                $('div.error_content').html("Value must be greater than 0.")
                                disable_add_to_cart()
                            } else if (data.error == "true") {
                                tenure_value_div.addClass("invalid");
                                $('div.error_content').html("Value must be less than or equal to " + data.max_value + ".")
                                disable_add_to_cart()
                                event.preventDefault()
                            } else if (data.error == "false") {
                                if (tenure_value_div.hasClass("invalid")) {
                                    tenure_value_div.removeClass("invalid");
                                    $('div.error_content').html("")
                                }
                                $("#check_tenure_price").html(data.tenure_price)
                                $('#custom_tenure_price').val(data.tenure_price)
                                enable_add_to_cart()
                                // if(event.isDefaultPrevented()){
                                //     $form.submit();
                                // }
                            }
                            $('.rental_loader').hide();
                        });
                    }
                }
            }, 200, true));

        $('#tenure_value , #tenure_uom ').on('change keyup keypress', function (event) {
            if (is_rental_product) {
                var $form = $(this).closest('form');
                var tenure_uom_id = parseInt($("select#tenure_uom option:selected").val())
                var tenure_value_div = $('#tenure_value')
                var tenure_value = tenure_value_div.val()
                var product_id = parseInt($form.find('input[type="hidden"][name="product_id"]').first().val());
                if (tenure_value === '') {
                    tenure_value_div.addClass("invalid");
                    $('div.error_content').html("Please enter a valid value")
                    disable_add_to_cart()
                }
                if (!isNaN(tenure_uom_id) && tenure_value != '' && document.getElementById("custom").checked == true) {
                    $('.rental_loader').show();
                    ajax.jsonRpc("/get/tenure/price", 'call', {
                        'tenure_uom_id': tenure_uom_id,
                        'tenure_value': tenure_value,
                        'product_id': product_id,
                    }).then(function (data) {
                        if (tenure_value <= 0) {
                            tenure_value_div.addClass("invalid");
                            $('div.error_content').html("Value must be greater than 0.")
                            disable_add_to_cart()
                        } else if (data.error == "true") {
                            tenure_value_div.addClass("invalid");
                            $('div.error_content').html("Value must be less than or equal to " + data.max_value + ".")
                            disable_add_to_cart()
                        } else if (data.error == "false") {
                            if (tenure_value_div.hasClass("invalid")) {
                                tenure_value_div.removeClass("invalid");
                                $('div.error_content').html("")
                            }
                            $("#check_tenure_price").html(data.tenure_price)
                            $('#custom_tenure_price').val(data.tenure_price)
                            enable_add_to_cart()
                        }
                        $('.rental_loader').hide();
                    });
                }
            }
        });
    });
});
