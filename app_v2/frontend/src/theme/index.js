import {createMuiTheme} from '@material-ui/core/styles';

export const theme = createMuiTheme({
    typography: {
        useNextVariants: true,
    },
    palette: {
        primary: {
            main: '#009688',
        }
    },
});