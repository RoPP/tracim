# Error code format
# 1xxx: not found error
# 2xxx: validation error
# 3xxx: conflict error
# 4xxx: authentication and authorization
# 9xxx: core errors(family of error code reserved
# for unclassable errors or very low level errors)


# Tracim Not found Error
USER_NOT_FOUND = 1001
WORKSPACE_NOT_FOUND = 1002
CONTENT_NOT_FOUND = 1003
PARENT_NOT_FOUND = 1004
USER_ROLE_NOT_FOUND = 1005
# Preview Based
UNAVAILABLE_PREVIEW_TYPE = 1011
PAGE_OF_PREVIEW_NOT_FOUND = 1012
UNAIVALABLE_PREVIEW = 1013

# Validation Error
GENERIC_SCHEMA_VALIDATION_ERROR = 2001
INTERNAL_TRACIM_VALIDATION_ERROR = 2002
# Not in Tracim Request #
USER_NOT_IN_TRACIM_REQUEST = 2011
WORKSPACE_NOT_IN_TRACIM_REQUEST = 2012
CONTENT_NOT_IN_TRACIM_REQUEST = 2013
# Invalid ID #
USER_INVALID_USER_ID = 2021
WORKSPACE_INVALID_ID = 2022
CONTENT_INVALID_ID = 2023
COMMENT_INVALID_ID = 2024

# Other #
CONTENT_TYPE_NOT_ALLOWED = 2031
WORKSPACE_DO_NOT_MATCH = 2032
PREVIEW_DIM_NOT_ALLOWED = 2033
WRONG_USER_PASSWORD = 2034
PASSWORD_DO_NOT_MATCH = 2035
EMAIL_ALREADY_EXIST_IN_DB = 2036
# deprecated params
EMAIL_VALIDATION_FAILED = 2037

UNALLOWED_SUBCONTENT = 2038
INVALID_RESET_PASSWORD_TOKEN = 2039
EXPIRED_RESET_PASSWORD_TOKEN = 2040
SAME_VALUE_ERROR = 2041
USER_NOT_ACTIVE = 2042
USER_DELETED = 2043
CONTENT_IN_NOT_EDITABLE_STATE = 2044
NOTIFICATION_SENDING_FAILED = 2045
NOTIFICATION_DISABLED_CANT_RESET_PASSWORD = 2046
NOTIFICATION_DISABLED_CANT_NOTIFY_NEW_USER = 2047
# Conflict Error
USER_ALREADY_EXIST = 3001
CONTENT_FILENAME_ALREADY_USED_IN_FOLDER = 3002
USER_CANT_DISABLE_HIMSELF = 3003
USER_CANT_DELETE_HIMSELF = 3004
USER_CANT_REMOVE_IS_OWN_ROLE_IN_WORKSPACE = 3005
USER_CANT_CHANGE_IS_OWN_PROFILE = 3006
WORKSPACE_LABEL_ALREADY_USED = 3007
USER_ROLE_ALREADY_EXIST = 3008

# Auth Error
AUTHENTICATION_FAILED = 4001
# Right Error
INSUFFICIENT_USER_PROFILE = 4002
INSUFFICIENT_USER_ROLE_IN_WORKSPACE = 4003
