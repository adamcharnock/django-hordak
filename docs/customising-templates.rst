Customising Templates
=====================

The easiest way to modify Hordak's default interface is to customise the default
templates.

.. note::

    This provides a basic level of customisation. For more control you will
    need to extend the :ref:`views <api_views>`, or create entirely new views of your own which
    build on Hordak's :ref:`models <api_models>`.

Hordak's templates can be found in `hordak/templates/hordak`_. You can override these templates by
creating similarly named files in your app's own ``templates`` directory.

For example, if you wish to override ``hordak/account_list.html``, you should
create the file ``hordak/account_list.html`` within your own app's template directory. Your template will
then be used by Django rather than the original.

.. important::

    By default Django searches for templates in each app's ``templates`` directory. It does
    this in the order listed in ``INSTALLED_APPS``. Therefore, **your app must appear before 'hordak'
    in 'INSTALLED_APPS'**.

.. _hordak/templates/hordak: https://github.com/adamcharnock/django-hordak/tree/master/hordak/templates/hordak
