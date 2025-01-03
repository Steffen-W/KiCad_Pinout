# -*- coding: utf-8 -*-

###########################################################################
## Python code generated with wxFormBuilder (version 4.2.1-0-g80c4cb6)
## http://www.wxformbuilder.org/
##
## PLEASE DO *NOT* EDIT THIS FILE!
###########################################################################

import wx
import wx.xrc

###########################################################################
## Class GUI_Dialog
###########################################################################

class GUI_Dialog ( wx.Dialog ):

	def __init__( self, parent ):
		wx.Dialog.__init__ ( self, parent, id = wx.ID_ANY, title = u"Pinout result", pos = wx.DefaultPosition, size = wx.Size( 600,600 ), style = wx.DEFAULT_DIALOG_STYLE|wx.RESIZE_BORDER )

		self.SetSizeHints( wx.Size( 300,300 ), wx.DefaultSize )

		gbSizer1 = wx.GridBagSizer( 0, 0 )
		gbSizer1.SetFlexibleDirection( wx.BOTH )
		gbSizer1.SetNonFlexibleGrowMode( wx.FLEX_GROWMODE_SPECIFIED )

		bSizer2 = wx.BoxSizer( wx.VERTICAL )

		bSizer4 = wx.BoxSizer( wx.HORIZONTAL )

		self.m_staticText11 = wx.StaticText( self, wx.ID_ANY, u"Select output format", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.m_staticText11.Wrap( -1 )

		bSizer4.Add( self.m_staticText11, 0, wx.ALIGN_CENTER|wx.ALL, 5 )

		output_formatChoices = [ u"List", u"CSV", u"HTML table", u"Markdown table", u"C/C++ code (#define)", u"C/C++ code (enum)", u"Python (dict)", u"WireViz ", u"FPGA (XDC format)", u"FPGA (PDC format)" ]
		self.output_format = wx.Choice( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, output_formatChoices, 0 )
		self.output_format.SetSelection( 0 )
		bSizer4.Add( self.output_format, 1, wx.ALL, 5 )

		self.m_buttonUpdate = wx.Button( self, wx.ID_ANY, u"Update", wx.DefaultPosition, wx.DefaultSize, 0 )
		bSizer4.Add( self.m_buttonUpdate, 0, wx.ALL, 5 )


		bSizer2.Add( bSizer4, 1, wx.EXPAND, 5 )

		self.m_staticline1 = wx.StaticLine( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.LI_HORIZONTAL )
		bSizer2.Add( self.m_staticline1, 0, wx.ALL|wx.EXPAND, 5 )

		gSizer1 = wx.GridSizer( 0, 2, 0, 0 )

		self.m_staticText2 = wx.StaticText( self, wx.ID_ANY, u"Start sequence\n{reference}, {value}, {description}", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_CENTER_HORIZONTAL )
		self.m_staticText2.Wrap( -1 )

		gSizer1.Add( self.m_staticText2, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_CENTER_HORIZONTAL, 5 )

		self.m_text_start = wx.TextCtrl( self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, wx.TE_MULTILINE )
		gSizer1.Add( self.m_text_start, 1, wx.ALL|wx.EXPAND, 5 )

		self.m_staticText6 = wx.StaticText( self, wx.ID_ANY, u"Pin sequence\n{pin_function}, {netname}, \n{number}, {pin_type}, {connected}", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_CENTER_HORIZONTAL )
		self.m_staticText6.Wrap( -1 )

		gSizer1.Add( self.m_staticText6, 0, wx.ALL|wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL, 5 )

		self.m_text_pin = wx.TextCtrl( self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, wx.TE_MULTILINE )
		gSizer1.Add( self.m_text_pin, 0, wx.ALL|wx.EXPAND, 5 )

		self.m_staticText7 = wx.StaticText( self, wx.ID_ANY, u"End sequence\n{reference}, {value}, {description}", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_CENTER_HORIZONTAL )
		self.m_staticText7.Wrap( -1 )

		gSizer1.Add( self.m_staticText7, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_CENTER_HORIZONTAL, 5 )

		self.m_text_end = wx.TextCtrl( self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, wx.TE_MULTILINE )
		gSizer1.Add( self.m_text_end, 0, wx.ALL|wx.EXPAND, 5 )


		bSizer2.Add( gSizer1, 0, wx.EXPAND, 5 )


		gbSizer1.Add( bSizer2, wx.GBPosition( 1, 0 ), wx.GBSpan( 1, 1 ), wx.EXPAND, 5 )

		self.result = wx.TextCtrl( self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, wx.TE_MULTILINE|wx.TE_READONLY|wx.VSCROLL )
		self.result.SetFont( wx.Font( 10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, False, "Monospace" ) )
		self.result.SetToolTip( u"Result (copy-paste this)" )

		gbSizer1.Add( self.result, wx.GBPosition( 0, 0 ), wx.GBSpan( 1, 1 ), wx.ALL|wx.EXPAND, 5 )


		gbSizer1.AddGrowableCol( 0 )
		gbSizer1.AddGrowableRow( 0 )

		self.SetSizer( gbSizer1 )
		self.Layout()

		self.Centre( wx.BOTH )

		# Connect Events
		self.output_format.Bind( wx.EVT_CHOICE, self.change_format )
		self.m_buttonUpdate.Bind( wx.EVT_BUTTON, self.update )

	def __del__( self ):
		pass


	# Virtual event handlers, override them in your derived class
	def change_format( self, event ):
		event.Skip()

	def update( self, event ):
		event.Skip()


