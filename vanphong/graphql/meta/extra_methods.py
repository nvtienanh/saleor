def extra_room_actions(instance, info, **data):
    info.context.plugins.room_updated(instance)


MODEL_EXTRA_METHODS = {"Room": extra_room_actions}
