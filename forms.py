from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField

class addPackage(FlaskForm):
    packageNumber = StringField('Insert Package Number')
    packageName = StringField('Insert Package NickName')
    carrier = SelectField(u'Please select the package carrier', choices=['UPS', 'FedEx', 'USPS'])
    submit = SubmitField('Add Pakcage')

class packageDetail(FlaskForm):
    packageNumber = StringField()
    submit = SubmitField('View Details')