var argv         = require('minimist')(process.argv.slice(2));
var autoprefixer = require('gulp-autoprefixer');
var chmod        = require('gulp-chmod');
var concat       = require('gulp-concat');
var gulp         = require('gulp');
var gulpif       = require('gulp-if');
var jade         = require('gulp-jade');
var livereload   = require('gulp-livereload');
var plumber      = require('gulp-plumber');
var rename       = require('gulp-rename');
var sass         = require('gulp-sass');
var sourcemaps   = require('gulp-sourcemaps');
var uglify       = require('gulp-uglify');
var cache        = require('gulp-cached');

var enabled = {
    uglify: argv.production,
    maps: argv.production,
    failCheck: argv.production,
    prettyPug: !argv.production,
    liveReload: !argv.production
};


/* CSS */
gulp.task('styles', function() {
    gulp.src('src/styles/**/*.sass')
        .pipe(gulpif(enabled.failCheck, plumber()))
        .pipe(gulpif(enabled.maps, sourcemaps.init()))
        .pipe(sass({
            outputStyle: 'compressed'}
            ))
        .pipe(autoprefixer("last 3 versions"))
        .pipe(gulpif(enabled.maps, sourcemaps.write(".")))
        .pipe(gulp.dest('flamenco/static/assets/css'))
        .pipe(gulpif(enabled.liveReload, livereload()));
});


/* Templates - Jade */
gulp.task('templates', function() {
    gulp.src('src/templates/**/*.jade')
        .pipe(gulpif(enabled.failCheck, plumber()))
        .pipe(cache('templating'))
        .pipe(jade({
            pretty: enabled.prettyPug
        }))
        .pipe(gulp.dest('flamenco/templates/'))
        .pipe(gulpif(enabled.liveReload, livereload()));
});


/* Individual Uglified Scripts */
gulp.task('scripts', function() {
    gulp.src('src/scripts/*.js')
        .pipe(gulpif(enabled.failCheck, plumber()))
        .pipe(cache('scripting'))
        .pipe(gulpif(enabled.maps, sourcemaps.init()))
        .pipe(gulpif(enabled.uglify, uglify()))
        .pipe(rename({suffix: '.min'}))
        .pipe(gulpif(enabled.maps, sourcemaps.write(".")))
        .pipe(chmod(644))
        .pipe(gulp.dest('flamenco/static/assets/js/generated/'))
        .pipe(gulpif(enabled.liveReload, livereload()));
});


/* Collection of scripts in src/scripts/tutti/ to merge into tutti.min.js */
/* Since it's always loaded, it's only for functions that we want site-wide */
gulp.task('scripts_tutti', function() {
    gulp.src('src/scripts/tutti/**/*.js')
        .pipe(gulpif(enabled.failCheck, plumber()))
        .pipe(gulpif(enabled.maps, sourcemaps.init()))
        .pipe(concat("tutti.min.js"))
        .pipe(gulpif(enabled.uglify, uglify()))
        .pipe(gulpif(enabled.maps, sourcemaps.write(".")))
        .pipe(chmod(644))
        .pipe(gulp.dest('flamenco/static/assets/js/generated/'))
        .pipe(gulpif(enabled.liveReload, livereload()));
});


// While developing, run 'gulp watch'
gulp.task('watch',function() {
    // Only listen for live reloads if ran with --livereload
    if (argv.livereload){
        livereload.listen();
    }

    gulp.watch('src/styles/**/*.sass',['styles']);
    gulp.watch('src/templates/**/*.jade',['templates']);
    gulp.watch('src/scripts/*.js',['scripts']);
    gulp.watch('src/scripts/tutti/*.js',['scripts_tutti']);
});


// Run 'gulp' to build everything at once
gulp.task('default', ['styles', 'templates', 'scripts', 'scripts_tutti']);
